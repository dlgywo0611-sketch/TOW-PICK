"""Integration tests for P0 balanced recommendation, with real JWT auth."""

import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
import models
from auth import hash_password
from database import Base


class BalancedRecommendationAPITests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.sessions = sessionmaker(autoflush=False, autocommit=False, bind=self.engine)
        Base.metadata.create_all(self.engine)
        self.password = "p0-balanced-test-password"
        with self.sessions() as db:
            c1 = models.Couple(invite_code="BALANCE1")
            c2 = models.Couple(invite_code="BALANCE2")
            db.add_all([c1, c2]); db.flush()
            u = [
                models.User(email="ba@example.test", nickname="A",
                            hashed_password=hash_password(self.password), couple_id=c1.id),
                models.User(email="bb@example.test", nickname="B",
                            hashed_password=hash_password(self.password), couple_id=c1.id),
                models.User(email="bc@example.test", nickname="C",
                            hashed_password=hash_password(self.password), couple_id=c2.id),
                models.User(email="bd@example.test", nickname="D",
                            hashed_password=hash_password(self.password), couple_id=c2.id),
                models.User(email="solo-balanced@example.test", nickname="Solo",
                            hashed_password=hash_password(self.password), couple_id=None),
            ]
            db.add_all(u); db.flush()
            decision = models.Decision(couple_id=c1.id, created_by_id=u[0].id,
                                       title="저녁 식사", status="open")
            other = models.Decision(couple_id=c2.id, created_by_id=u[2].id,
                                    title="다른 커플", status="open")
            db.add_all([decision, other]); db.flush()
            self.did = decision.id
            self.other_did = other.id
            db.commit()

        def db_override():
            with self.sessions() as db:
                yield db

        main.app.dependency_overrides[main.get_db] = db_override
        self.client = TestClient(main.app)
        self.headers = {}
        for key, email in {
            "a": "ba@example.test", "b": "bb@example.test",
            "c": "bc@example.test", "d": "bd@example.test",
            "solo": "solo-balanced@example.test",
        }.items():
            reply = self.client.post("/token", data={"username": email,
                                                      "password": self.password})
            self.assertEqual(reply.status_code, 200, reply.text)
            self.headers[key] = {"Authorization":
                                 "Bearer " + reply.json()["access_token"]}

    def tearDown(self):
        self.client.close()
        main.app.dependency_overrides.clear()
        self.engine.dispose()

    def condition(self, key, budget=30000, time="토 18:00-20:00",
                  pref="", avoid=""):
        reply = self.client.put(
            f"/decisions/{self.did}/conditions/me",
            json={"max_budget": budget, "available_time": time,
                  "preferences": pref, "avoidances": avoid},
            headers=self.headers[key],
        )
        self.assertEqual(reply.status_code, 200, reply.text)

    @staticmethod
    def option(title, cost=18000, time="토 18:00-20:00", tags=None):
        return {"title": title, "estimated_total_cost_krw": cost,
                "time_slot": time, "tags": tags or []}

    def recommend(self, options=None, key="a", did=None):
        if options is None:
            options = [self.option("한식"), self.option("전시", 14000)]
        return self.client.post(
            f"/decisions/{did if did is not None else self.did}/recommendations",
            json={"options": options}, headers=self.headers[key],
        )

    def test_full_flow_creates_v1_then_both_approve(self):
        self.condition("a", 30000, pref="조용한 곳,한식")
        self.condition("b", 20000, pref="조용한 곳")
        response = self.recommend([
            self.option("A preference only", 12000, tags=["한식"]),
            self.option("balanced choice", 18000, tags=["조용한 곳"]),
        ])
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(set(body), {"policy_version", "message", "candidate"})
        self.assertEqual(body["policy_version"], "balanced_rules_v1")
        self.assertTrue(body["candidate"]["content"].startswith("balanced choice /"))
        self.assertIn("시연용", body["candidate"]["content"])
        self.assertEqual(body["candidate"]["version"], 1)
        self.assertTrue(body["candidate"]["is_current"])
        self.assertNotIn("조용한 곳", response.text)
        self.assertNotIn("max_budget", response.text)

        cid = body["candidate"]["id"]
        for key in ("a", "b"):
            approval = self.client.post(f"/candidates/{cid}/approve",
                                        headers=self.headers[key])
            self.assertEqual(approval.status_code, 201, approval.text)
        detail = self.client.get(f"/decisions/{self.did}",
                                 headers=self.headers["b"]).json()
        self.assertTrue(detail["confirmed"])
        self.assertEqual(detail["current_candidate"]["approval_count"], 2)

    def test_uses_each_persons_ceiling_on_two_person_total(self):
        self.condition("a", 30000)
        self.condition("b", 20000)
        reply = self.recommend([
            self.option("Over B cap", 25000),
            self.option("Within both", 19000),
        ])
        self.assertEqual(reply.status_code, 201, reply.text)
        self.assertTrue(reply.json()["candidate"]["content"].startswith("Within both /"))

    def test_available_time_exact_match_and_avoidance(self):
        self.condition("a", time="토 18:00-20:00, 일 14:00-16:00", avoid="매운 음식")
        self.condition("b", time="토 18:00-20:00")
        reply = self.recommend([
            self.option("No shared time", 18000, time="일 14:00-16:00"),
            self.option("Avoided", 18000, tags=["매운 음식"]),
            self.option("OK", 18000),
        ])
        self.assertEqual(reply.status_code, 201, reply.text)
        self.assertTrue(reply.json()["candidate"]["content"].startswith("OK /"))

    def test_both_conditions_required_no_attempt_consumed(self):
        self.condition("a")
        rejected = self.recommend()
        self.assertEqual(rejected.status_code, 409)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(models.DecisionRecommendationAttempt.id))), 0)
        self.condition("b")
        allowed = self.recommend()
        self.assertEqual(allowed.status_code, 201, allowed.text)

    def test_one_shot_success_and_not_overwriting_existing_candidate(self):
        self.condition("a"); self.condition("b")
        chosen = self.recommend()
        self.assertEqual(chosen.status_code, 201, chosen.text)
        again = self.recommend()
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()["detail"], "Recommendation already attempted for this decision")
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(models.DecisionRecommendationAttempt.id))), 1)
            self.assertEqual(db.scalar(select(func.count(models.DecisionCandidate.id))), 1)

    def test_no_eligible_option_consumes_attempt_but_manual_candidate_works(self):
        self.condition("a", 5000); self.condition("b", 5000)
        no_match = self.recommend([self.option("A", 12000), self.option("B", 16000)])
        self.assertEqual(no_match.status_code, 409, no_match.text)
        self.assertEqual(no_match.json()["detail"],
                         "No mutually suitable option; try a manual candidate")
        with self.sessions() as db:
            attempt = db.scalar(select(models.DecisionRecommendationAttempt))
            self.assertEqual(attempt.outcome, "no_match")
            self.assertIsNone(attempt.candidate_id)
            self.assertEqual(db.scalar(select(func.count(models.DecisionCandidate.id))), 0)
        self.assertEqual(self.recommend().status_code, 409)
        manually = self.client.post(f"/decisions/{self.did}/candidates",
                                    json={"content": "무료 산책"}, headers=self.headers["a"])
        self.assertEqual(manually.status_code, 201, manually.text)

    def test_already_manual_candidate_refuses_recommendation(self):
        self.condition("a"); self.condition("b")
        manual = self.client.post(f"/decisions/{self.did}/candidates",
                                  json={"content": "기존 후보"}, headers=self.headers["a"])
        self.assertEqual(manual.status_code, 201, manual.text)
        rejected = self.recommend()
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(rejected.json()["detail"],
                         "Recommendation only available before first candidate")

    def test_wrong_couple_missing_and_unauthed(self):
        options = [self.option("a"), self.option("b")]
        stranger = self.recommend(options, key="c")
        self.assertEqual(stranger.status_code, 403)
        missing = self.recommend(options, did=999999)
        self.assertEqual(missing.status_code, 404)
        solo = self.recommend(options, key="solo")
        self.assertEqual(solo.status_code, 409)
        anonymous = self.client.post(f"/decisions/{self.did}/recommendations",
                                     json={"options": options})
        self.assertEqual(anonymous.status_code, 401)

    def test_invalid_request_rejected_without_consuming_attempt(self):
        self.condition("a"); self.condition("b")
        choices = [self.option("A"), self.option("B")]
        for body in [
            {"options": []},
            {"options": [self.option("dup"), self.option("DUP")]},
            {"options": [self.option("A", -1), self.option("B")]},
            {"options": [self.option(" "), self.option("B")]},
            {"options": [self.option("A", tags=[" "]), self.option("B")]},
            {"options": choices, "user_id": 123},
            {"options": choices, "couple_id": 777},
        ]:
            with self.subTest(body=body):
                reply = self.client.post(f"/decisions/{self.did}/recommendations",
                                         json=body, headers=self.headers["a"])
                self.assertEqual(reply.status_code, 422, reply.text)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(models.DecisionRecommendationAttempt.id))), 0)

    def test_closed_decision_cannot_recommend(self):
        self.condition("a"); self.condition("b")
        with self.sessions() as db:
            decision = db.get(models.Decision, self.did)
            decision.status = "confirmed"
            db.commit()
        self.assertEqual(self.recommend().status_code, 409)


if __name__ == "__main__":
    unittest.main()
