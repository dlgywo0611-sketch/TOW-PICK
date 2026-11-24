import unittest

from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import main
import models
from database import Base


class DecisionReadApiTests(unittest.TestCase):
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
            couple_a = models.Couple(invite_code="COUPLEA1")
            couple_b = models.Couple(invite_code="COUPLEB1")
            db.add_all([couple_a, couple_b])
            db.flush()

            users = [
                models.User(
                    email="a@example.com",
                    nickname="a",
                    hashed_password="unused",
                    couple_id=couple_a.id,
                ),
                models.User(
                    email="b@example.com",
                    nickname="b",
                    hashed_password="unused",
                    couple_id=couple_a.id,
                ),
                models.User(
                    email="c@example.com",
                    nickname="c",
                    hashed_password="unused",
                    couple_id=couple_b.id,
                ),
                models.User(
                    email="solo@example.com",
                    nickname="solo",
                    hashed_password="unused",
                    couple_id=None,
                ),
            ]
            db.add_all(users)
            db.flush()

            decision = models.Decision(
                couple_id=couple_a.id,
                created_by_id=users[0].id,
                title="Dinner",
                status="open",
            )
            empty_decision = models.Decision(
                couple_id=couple_a.id,
                created_by_id=users[1].id,
                title="No candidate yet",
                status="open",
            )
            other_decision = models.Decision(
                couple_id=couple_b.id,
                created_by_id=users[2].id,
                title="Private decision",
                status="open",
            )
            db.add_all([decision, empty_decision, other_decision])
            db.commit()

            self.user_a_id = users[0].id
            self.user_b_id = users[1].id
            self.other_user_id = users[2].id
            self.solo_user_id = users[3].id
            self.decision_id = decision.id
            self.empty_decision_id = empty_decision.id
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

    def test_list_returns_only_current_couple_in_newest_first_order(self):
        response = self.client.get("/decisions")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            [item["id"] for item in payload],
            [self.empty_decision_id, self.decision_id],
        )
        self.assertNotIn(
            self.other_decision_id,
            [item["id"] for item in payload],
        )

    def test_authentication_is_required(self):
        del main.app.dependency_overrides[main.get_current_user]

        list_response = self.client.get("/decisions")
        detail_response = self.client.get(
            f"/decisions/{self.decision_id}"
        )

        self.assertEqual(list_response.status_code, 401)
        self.assertEqual(detail_response.status_code, 401)

    def test_both_couple_members_can_read_a_decision_without_candidate(self):
        for user_id in (self.user_a_id, self.user_b_id):
            self.current_user_id = user_id
            response = self.client.get(
                f"/decisions/{self.empty_decision_id}"
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIsNone(payload["current_candidate"])
            self.assertFalse(payload["confirmed"])

    def test_other_couple_is_forbidden_and_missing_decision_is_not_found(self):
        response = self.client.get(
            f"/decisions/{self.other_decision_id}"
        )
        missing_response = self.client.get("/decisions/999999")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(missing_response.status_code, 404)

    def test_user_without_couple_cannot_read_decisions(self):
        self.current_user_id = self.solo_user_id

        list_response = self.client.get("/decisions")
        detail_response = self.client.get(
            f"/decisions/{self.decision_id}"
        )

        self.assertEqual(list_response.status_code, 409)
        self.assertEqual(detail_response.status_code, 409)

    def test_latest_candidate_and_approval_state_until_confirmed(self):
        first_candidate = self.client.post(
            f"/decisions/{self.decision_id}/candidates",
            json={"content": "Pizza"},
        )
        second_candidate = self.client.post(
            f"/decisions/{self.decision_id}/candidates",
            json={"content": "Sushi"},
        )

        self.assertEqual(first_candidate.status_code, 201)
        self.assertEqual(second_candidate.status_code, 201)
        self.assertFalse(
            self._candidate(first_candidate.json()["id"]).is_current
        )

        candidate_id = second_candidate.json()["id"]
        response = self.client.get(f"/decisions/{self.decision_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["current_candidate"]["version"], 2)

        first_approval = self.client.post(
            f"/candidates/{candidate_id}/approve"
        )
        self.assertEqual(first_approval.status_code, 201)

        one_approval = self.client.get(
            f"/decisions/{self.decision_id}"
        ).json()
        self.assertEqual(
            one_approval["current_candidate"]["approval_count"],
            1,
        )
        self.assertEqual(
            [
                item["approved"]
                for item in one_approval["current_candidate"][
                    "member_approvals"
                ]
            ],
            [True, False],
        )
        self.assertFalse(one_approval["confirmed"])

        self.current_user_id = self.user_b_id
        second_approval = self.client.post(
            f"/candidates/{candidate_id}/approve"
        )
        self.assertEqual(second_approval.status_code, 201)

        confirmed = self.client.get(
            f"/decisions/{self.decision_id}"
        ).json()
        self.assertEqual(confirmed["status"], "confirmed")
        self.assertTrue(confirmed["confirmed"])
        self.assertEqual(
            confirmed["current_candidate"]["approval_count"],
            2,
        )
        self.assertTrue(
            all(
                item["approved"]
                for item in confirmed["current_candidate"][
                    "member_approvals"
                ]
            )
        )

    def _candidate(self, candidate_id: int) -> models.DecisionCandidate:
        with self.session_factory() as db:
            candidate = db.get(models.DecisionCandidate, candidate_id)
            self.assertIsNotNone(candidate)
            db.expunge(candidate)
            return candidate


if __name__ == "__main__":
    unittest.main()
