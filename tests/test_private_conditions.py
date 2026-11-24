import unittest

from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import main
import models
from database import Base


class PrivateConditionApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )
        Base.metadata.create_all(bind=self.engine)

        with self.session_factory() as db:
            couple_a = models.Couple(invite_code="PRIVATE1")
            couple_b = models.Couple(invite_code="PRIVATE2")
            db.add_all([couple_a, couple_b])
            db.flush()

            users = [
                models.User(
                    email="condition-a@example.test",
                    nickname="condition-a",
                    hashed_password="unused",
                    couple_id=couple_a.id,
                ),
                models.User(
                    email="condition-b@example.test",
                    nickname="condition-b",
                    hashed_password="unused",
                    couple_id=couple_a.id,
                ),
                models.User(
                    email="condition-c@example.test",
                    nickname="condition-c",
                    hashed_password="unused",
                    couple_id=couple_b.id,
                ),
                models.User(
                    email="condition-solo@example.test",
                    nickname="condition-solo",
                    hashed_password="unused",
                    couple_id=None,
                ),
            ]
            db.add_all(users)
            db.flush()

            decision = models.Decision(
                couple_id=couple_a.id,
                created_by_id=users[0].id,
                title="Private dinner conditions",
                status="open",
            )
            other_decision = models.Decision(
                couple_id=couple_b.id,
                created_by_id=users[2].id,
                title="Other couple decision",
                status="open",
            )
            db.add_all([decision, other_decision])
            db.commit()

            self.user_a_id = users[0].id
            self.user_b_id = users[1].id
            self.other_user_id = users[2].id
            self.solo_user_id = users[3].id
            self.decision_id = decision.id
            self.other_decision_id = other_decision.id

        self.current_user_id = self.user_a_id

        def override_get_db():
            db = self.session_factory()
            try:
                yield db
            finally:
                db.close()

        def override_current_user(
            db: Session = Depends(override_get_db),
        ):
            return db.get(models.User, self.current_user_id)

        main.app.dependency_overrides[main.get_db] = override_get_db
        main.app.dependency_overrides[
            main.get_current_user
        ] = override_current_user
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        main.app.dependency_overrides.clear()
        self.engine.dispose()

    def test_each_member_saves_and_reads_only_own_conditions(self):
        response_a = self._put(self._payload("quiet table", 50000))
        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(response_a.json()["user_id"], self.user_a_id)

        self.current_user_id = self.user_b_id
        before_b_submits = self.client.get(self._me_path())
        self.assertEqual(before_b_submits.status_code, 404)
        self.assertEqual(
            before_b_submits.json()["detail"],
            "Conditions not found",
        )

        response_b = self._put(self._payload("window seat", 35000))
        self.assertEqual(response_b.status_code, 200)
        self.assertEqual(response_b.json()["user_id"], self.user_b_id)
        self.assertEqual(
            self.client.get(self._me_path()).json()["preferences"],
            "window seat",
        )

        self.current_user_id = self.user_a_id
        my_condition = self.client.get(self._me_path())
        self.assertEqual(my_condition.status_code, 200)
        self.assertEqual(my_condition.json()["preferences"], "quiet table")

    def test_status_shares_only_submission_flags(self):
        secret_preference = "private preference must not be shared"
        self._put(self._payload(secret_preference, 50000))

        self.current_user_id = self.user_b_id
        one_submitted = self.client.get(self._status_path())
        self.assertEqual(one_submitted.status_code, 200)
        payload = one_submitted.json()
        self.assertEqual(payload["submitted_count"], 1)
        self.assertEqual(
            [item["submitted"] for item in payload["member_conditions"]],
            [True, False],
        )
        self.assertNotIn(secret_preference, one_submitted.text)
        for item in payload["member_conditions"]:
            self.assertEqual(set(item), {"user_id", "submitted"})

        self._put(self._payload("my own preference", 30000))
        both_submitted = self.client.get(self._status_path()).json()
        self.assertEqual(both_submitted["submitted_count"], 2)
        self.assertTrue(
            all(
                item["submitted"]
                for item in both_submitted["member_conditions"]
            )
        )

    def test_other_couple_is_forbidden_for_all_condition_endpoints(self):
        self.current_user_id = self.other_user_id

        responses = [
            self._put(self._payload("other", 10000)),
            self.client.get(self._me_path()),
            self.client.get(self._status_path()),
        ]
        self.assertTrue(
            all(response.status_code == 403 for response in responses)
        )
        self.assertTrue(
            all(
                response.json()["detail"]
                == "You cannot access this decision"
                for response in responses
            )
        )

    def test_invalid_input_and_identity_injection_are_rejected(self):
        invalid_payloads = [
            self._payload("negative budget", -1),
            {
                **self._payload("blank time", 10000),
                "available_time": "   ",
            },
            {
                **self._payload("identity injection", 10000),
                "user_id": self.user_b_id,
                "couple_id": 999,
            },
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self._put(payload)
                self.assertEqual(response.status_code, 422)

    def test_authentication_is_required(self):
        del main.app.dependency_overrides[main.get_current_user]

        responses = [
            self.client.put(
                self._me_path(),
                json=self._payload("auth", 10000),
            ),
            self.client.get(self._me_path()),
            self.client.get(self._status_path()),
        ]
        self.assertTrue(
            all(response.status_code == 401 for response in responses)
        )

    def test_repeated_put_updates_one_row(self):
        created = self._put(self._payload("first", 50000))
        updated = self._put(self._payload("second", 70000))

        self.assertEqual(created.status_code, 200)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(created.json()["id"], updated.json()["id"])
        self.assertEqual(updated.json()["max_budget"], 70000)
        self.assertEqual(updated.json()["preferences"], "second")

        with self.session_factory() as db:
            count = db.scalar(
                select(func.count(models.DecisionCondition.id)).where(
                    models.DecisionCondition.decision_id == self.decision_id,
                    models.DecisionCondition.user_id == self.user_a_id,
                )
            )
        self.assertEqual(count, 1)

    def test_conditions_are_locked_after_candidate_creation(self):
        original = self._put(self._payload("before candidate", 50000))
        self.assertEqual(original.status_code, 200)

        candidate = self.client.post(
            f"/decisions/{self.decision_id}/candidates",
            json={"content": "candidate using frozen conditions"},
        )
        self.assertEqual(candidate.status_code, 201)

        blocked_update = self._put(
            self._payload("after candidate", 90000)
        )
        self.assertEqual(blocked_update.status_code, 409)
        self.assertEqual(
            blocked_update.json()["detail"],
            "Conditions cannot be changed after candidate creation",
        )

        self.current_user_id = self.user_b_id
        blocked_first_submission = self._put(
            self._payload("late submission", 20000)
        )
        self.assertEqual(blocked_first_submission.status_code, 409)

        self.current_user_id = self.user_a_id
        unchanged = self.client.get(self._me_path()).json()
        self.assertEqual(unchanged["preferences"], "before candidate")
        self.assertEqual(unchanged["max_budget"], 50000)

    def test_missing_decision_and_user_without_couple(self):
        missing = self.client.get("/decisions/999999/conditions/status")
        self.assertEqual(missing.status_code, 404)

        self.current_user_id = self.solo_user_id
        solo = self.client.get(self._status_path())
        self.assertEqual(solo.status_code, 409)
        self.assertEqual(
            solo.json()["detail"],
            "User does not belong to a couple",
        )

    def _payload(self, preference: str, max_budget: int) -> dict:
        return {
            "max_budget": max_budget,
            "available_time": "Saturday 18:00-21:00",
            "preferences": preference,
            "avoidances": "long waiting time",
        }

    def _me_path(self) -> str:
        return f"/decisions/{self.decision_id}/conditions/me"

    def _status_path(self) -> str:
        return f"/decisions/{self.decision_id}/conditions/status"

    def _put(self, payload: dict):
        return self.client.put(self._me_path(), json=payload)


if __name__ == "__main__":
    unittest.main()
