"""JWT and couple API regression checks against an isolated SQLite database."""

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
from threading import Barrier
from pathlib import Path

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import auth
import main
import models
from database import Base


class AuthCoupleApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)

        def test_db():
            with self.sessions() as db:
                yield db

        main.app.dependency_overrides[main.get_db] = test_db
        self.client = TestClient(main.app)
        self.password = "auth-couple-test-password"

    def tearDown(self):
        self.client.close()
        main.app.dependency_overrides.clear()
        self.engine.dispose()

    def register(self, email):
        return self.client.post(
            "/users", json={"email": email, "nickname": email.split("@")[0],
                            "password": self.password},
        )

    def login(self, email, password=None):
        return self.client.post(
            "/token", data={"username": email,
                            "password": password or self.password},
        )

    def headers(self, email):
        token = self.login(email)
        self.assertEqual(token.status_code, 200, token.text)
        return {"Authorization": f"Bearer {token.json()['access_token']}"}

    def test_register_login_failure_duplicate_and_current_user(self):
        a = self.register("a@example.test")
        b = self.register("b@example.test")
        self.assertEqual((a.status_code, b.status_code), (201, 201))
        self.assertNotEqual(a.json()["id"], b.json()["id"])
        self.assertEqual(self.register("a@example.test").status_code, 409)
        self.assertEqual(self.login("a@example.test", "wrong").status_code, 401)
        self.assertEqual(self.client.get("/users/me").status_code, 401)
        self.assertEqual(self.client.get("/users/me", headers={
            "Authorization": "Bearer invalid.token.value"
        }).status_code, 401)
        for email in ("a@example.test", "b@example.test"):
            me = self.client.get("/users/me", headers=self.headers(email))
            self.assertEqual(me.status_code, 200)
            self.assertEqual(me.json()["email"], email)

    def test_expired_token_and_logout_relogin(self):
        self.register("a@example.test")
        headers = self.headers("a@example.test")
        expired = jwt.encode(
            {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
             "jti": "expired-test-token"},
            auth.SECRET_KEY, algorithm=auth.ALGORITHM,
        )
        self.assertEqual(self.client.get("/users/me", headers={
            "Authorization": f"Bearer {expired}"
        }).status_code, 401)
        self.assertEqual(self.client.post("/logout", headers=headers).status_code, 200)
        revoked = self.client.get("/users/me", headers=headers)
        self.assertEqual(revoked.status_code, 401)
        self.assertEqual(revoked.json()["detail"], "Token has been revoked")
        self.assertEqual(self.client.get("/users/me", headers=self.headers(
            "a@example.test"
        )).status_code, 200)
        with self.sessions() as db:
            rows = db.scalars(select(models.RevokedToken)).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(rows[0].token_hash), 64)

    def test_invite_join_capacity_and_existing_user(self):
        for email in ("a@example.test", "b@example.test", "c@example.test"):
            self.assertEqual(self.register(email).status_code, 201)
        a, b, c = (self.headers(f"{letter}@example.test") for letter in "abc")
        created = self.client.post("/couples", headers=a)
        self.assertEqual(created.status_code, 201)
        code = created.json()["invite_code"]
        self.assertEqual(len(code), 8)
        self.assertEqual(self.client.post("/couples", headers=a).status_code, 409)
        self.assertEqual(self.client.post("/couples/join", headers=b, json={
            "invite_code": "NOTFOUND"
        }).status_code, 404)
        joined = self.client.post("/couples/join", headers=b, json={
            "invite_code": code.lower()
        })
        self.assertEqual(joined.status_code, 200)
        self.assertEqual(created.json()["id"], joined.json()["id"])
        self.assertEqual(self.client.get("/couples/me", headers=a).json()["id"],
                         self.client.get("/couples/me", headers=b).json()["id"])
        self.assertEqual(self.client.post("/couples/join", headers=b, json={
            "invite_code": code
        }).status_code, 409)
        self.assertEqual(self.client.post("/couples/join", headers=c, json={
            "invite_code": code
        }).status_code, 409)
        self.assertEqual(self.client.get("/couples/me", headers=c).status_code, 404)

    def test_other_couple_decision_is_forbidden(self):
        for email in ("a@example.test", "b@example.test", "c@example.test"):
            self.register(email)
        a, b, c = (self.headers(f"{letter}@example.test") for letter in "abc")
        own = self.client.post("/couples", headers=a)
        self.client.post("/couples/join", headers=b, json={
            "invite_code": own.json()["invite_code"]
        })
        self.client.post("/couples", headers=c)
        decision = self.client.post("/decisions", headers=a,
                                    json={"title": "private"})
        self.assertEqual(decision.status_code, 201)
        other = self.client.get(f"/decisions/{decision.json()['id']}", headers=c)
        self.assertEqual(other.status_code, 403)
        self.assertEqual(self.client.get("/decisions", headers=c).json(), [])

    def test_concurrent_join_keeps_two_member_capacity(self):
        with TemporaryDirectory() as temporary:
            db_path = Path(temporary) / "couple-test.db"
            engine = create_engine(
                f"sqlite:///{db_path.as_posix()}",
                connect_args={"check_same_thread": False, "timeout": 5},
            )
            Base.metadata.create_all(engine)
            sessions = sessionmaker(bind=engine)
            with sessions() as db:
                couple = models.Couple(invite_code="RACE0001")
                db.add(couple)
                db.flush()
                for letter in "abc":
                    db.add(models.User(
                        email=f"race-{letter}@example.test",
                        nickname=letter,
                        hashed_password=auth.hash_password(self.password),
                        couple_id=couple.id if letter == "a" else None,
                    ))
                db.commit()
                couple_id = couple.id

            def race_db():
                with sessions() as db:
                    yield db

            main.app.dependency_overrides[main.get_db] = race_db
            b = self.headers("race-b@example.test")
            c = self.headers("race-c@example.test")
            gate = Barrier(2)

            def join(headers):
                gate.wait()
                return self.client.post(
                    "/couples/join", headers=headers,
                    json={"invite_code": "RACE0001"},
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                future_b = pool.submit(join, b)
                future_c = pool.submit(join, c)
                responses = [future_b.result(), future_c.result()]
            self.assertEqual(sorted(item.status_code for item in responses),
                             [200, 409])
            with sessions() as db:
                members = db.scalars(select(models.User).where(
                    models.User.couple_id == couple_id
                )).all()
                self.assertEqual(len(members), 2)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
