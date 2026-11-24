import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
import models
from auth import hash_password
from database import Base


class PrivateConditionApiTests(unittest.TestCase):
    def setUp(self):
        self.password = "private-condition-test-password"
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
                    hashed_password=hash_password(self.password),
                    couple_id=couple_a.id,
                ),
                models.User(
                    email="condition-b@example.test",
                    nickname="condition-b",
                    hashed_password=hash_password(self.password),
                    couple_id=couple_a.id,
                ),
                models.User(
                    email="condition-c@example.test",
                    nickname="condition-c",
                    hashed_password=hash_password(self.password),
                    couple_id=couple_b.id,
                ),
                models.User(
                    email="condition-solo@example.test",
                    nickname="condition-solo",
                    hashed_password=hash_password(self.password),
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

        def override_get_db():
            db = self.session_factory()
            try:
                yield db
            finally:
                db.close()

        main.app.dependency_overrides[main.get_db] = override_get_db
        self.client = TestClient(main.app)
        self.headers = {
            self.user_a_id: self._login("condition-a@example.test"),
            self.user_b_id: self._login("condition-b@example.test"),
            self.other_user_id: self._login("condition-c@example.test"),
            self.solo_user_id: self._login("condition-solo@example.test"),
        }

    def tearDown(self):
        self.client.close()
        main.app.dependency_overrides.clear()
        self.engine.dispose()

    def test_each_member_saves_and_reads_only_own_conditions(self):
        response_a = self._put(
            self._payload("quiet table", 50000),
            self.user_a_id,
        )
        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(response_a.json()["user_id"], self.user_a_id)

        before_b_submits = self.client.get(
            self._me_path(),
            headers=self.headers[self.user_b_id],
        )
        self.assertEqual(before_b_submits.status_code, 404)
        self.assertEqual(
            before_b_submits.json()["detail"],
            "Conditions not found",
        )

        response_b = self._put(
            self._payload("window seat", 35000),
            self.user_b_id,
        )
        self.assertEqual(response_b.status_code, 200)
        self.assertEqual(response_b.json()["user_id"], self.user_b_id)
        self.assertEqual(
            self.client.get(
                self._me_path(),
                headers=self.headers[self.user_b_id],
            ).json()["preferences"],
            "window seat",
        )

        my_condition = self.client.get(
            self._me_path(),
            headers=self.headers[self.user_a_id],
        )
        self.assertEqual(my_condition.status_code, 200)
        self.assertEqual(my_condition.json()["preferences"], "quiet table")

    def test_status_shares_only_submission_flags(self):
        secret_preference = "private preference must not be shared"
        self._put(
            self._payload(secret_preference, 50000),
            self.user_a_id,
        )

        one_submitted = self.client.get(
            self._status_path(),
            headers=self.headers[self.user_b_id],
        )
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

        self._put(
            self._payload("my own preference", 30000),
            self.user_b_id,
        )
        both_submitted = self.client.get(
            self._status_path(),
            headers=self.headers[self.user_b_id],
        ).json()
        self.assertEqual(both_submitted["submitted_count"], 2)
        self.assertTrue(
            all(
                item["submitted"]
                for item in both_submitted["member_conditions"]
            )
        )

    def test_other_couple_is_forbidden_for_all_condition_endpoints(self):
        responses = [
            self._put(
                self._payload("other", 10000),
                self.other_user_id,
            ),
            self.client.get(
                self._me_path(),
                headers=self.headers[self.other_user_id],
            ),
            self.client.get(
                self._status_path(),
                headers=self.headers[self.other_user_id],
            ),
            self.client.post(
                f"/decisions/{self.decision_id}/candidates",
                json={"content": "other couple candidate"},
                headers=self.headers[self.other_user_id],
            ),
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
                response = self._put(payload, self.user_a_id)
                self.assertEqual(response.status_code, 422)

    def test_authentication_is_required(self):
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
        created = self._put(
            self._payload("first", 50000),
            self.user_a_id,
        )
        updated = self._put(
            self._payload("second", 70000),
            self.user_a_id,
        )

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

    def test_candidate_requires_both_conditions_and_locks_both_members(self):
        condition_a = self._put(
            self._payload("condition a", 50000),
            self.user_a_id,
        )
        self.assertEqual(condition_a.status_code, 200)

        blocked_candidate = self.client.post(
            f"/decisions/{self.decision_id}/candidates",
            json={"content": "candidate before both submit"},
            headers=self.headers[self.user_a_id],
        )
        self.assertEqual(blocked_candidate.status_code, 409)
        self.assertEqual(
            blocked_candidate.json()["detail"],
            "Both couple members must submit conditions before "
            "candidate creation",
        )

        condition_b = self._put(
            self._payload("condition b", 30000),
            self.user_b_id,
        )
        self.assertEqual(condition_b.status_code, 200)

        candidate = self.client.post(
            f"/decisions/{self.decision_id}/candidates",
            json={"content": "candidate using both conditions"},
            headers=self.headers[self.user_a_id],
        )
        self.assertEqual(candidate.status_code, 201)
        self.assertEqual(candidate.json()["version"], 1)
        self.assertTrue(candidate.json()["is_current"])

        for user_id in (self.user_a_id, self.user_b_id):
            with self.subTest(user_id=user_id):
                blocked_update = self._put(
                    self._payload("after candidate", 90000),
                    user_id,
                )
                self.assertEqual(blocked_update.status_code, 409)
                self.assertEqual(
                    blocked_update.json()["detail"],
                    "Conditions cannot be changed after candidate creation",
                )

    def test_candidate_versions_and_bilateral_approval_still_work(self):
        self._submit_both_conditions()

        first_candidate = self.client.post(
            f"/decisions/{self.decision_id}/candidates",
            json={"content": "first candidate"},
            headers=self.headers[self.user_a_id],
        )
        second_candidate = self.client.post(
            f"/decisions/{self.decision_id}/candidates",
            json={"content": "second candidate"},
            headers=self.headers[self.user_a_id],
        )

        self.assertEqual(first_candidate.status_code, 201)
        self.assertEqual(first_candidate.json()["version"], 1)
        self.assertEqual(second_candidate.status_code, 201)
        self.assertEqual(second_candidate.json()["version"], 2)
        with self.session_factory() as db:
            stored_first = db.get(
                models.DecisionCandidate,
                first_candidate.json()["id"],
            )
            self.assertFalse(stored_first.is_current)

        candidate_id = second_candidate.json()["id"]
        approval_a = self.client.post(
            f"/candidates/{candidate_id}/approve",
            headers=self.headers[self.user_a_id],
        )
        self.assertEqual(approval_a.status_code, 201)
        decision_after_a = self.client.get(
            f"/decisions/{self.decision_id}",
            headers=self.headers[self.user_a_id],
        ).json()
        self.assertFalse(decision_after_a["confirmed"])

        approval_b = self.client.post(
            f"/candidates/{candidate_id}/approve",
            headers=self.headers[self.user_b_id],
        )
        self.assertEqual(approval_b.status_code, 201)
        confirmed = self.client.get(
            f"/decisions/{self.decision_id}",
            headers=self.headers[self.user_b_id],
        ).json()
        self.assertTrue(confirmed["confirmed"])
        self.assertEqual(confirmed["status"], "confirmed")

    def test_missing_decision_and_user_without_couple(self):
        missing = self.client.get(
            "/decisions/999999/conditions/status",
            headers=self.headers[self.user_a_id],
        )
        self.assertEqual(missing.status_code, 404)

        solo = self.client.get(
            self._status_path(),
            headers=self.headers[self.solo_user_id],
        )
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

    def _login(self, email: str) -> dict[str, str]:
        response = self.client.post(
            "/token",
            data={"username": email, "password": self.password},
        )
        self.assertEqual(response.status_code, 200)
        return {
            "Authorization": f"Bearer {response.json()['access_token']}"
        }

    def _put(self, payload: dict, user_id: int):
        return self.client.put(
            self._me_path(),
            json=payload,
            headers=self.headers[user_id],
        )

    def _submit_both_conditions(self):
        response_a = self._put(
            self._payload("condition a", 50000),
            self.user_a_id,
        )
        response_b = self._put(
            self._payload("condition b", 30000),
            self.user_b_id,
        )
        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(response_b.status_code, 200)


if __name__ == "__main__":
    unittest.main()
