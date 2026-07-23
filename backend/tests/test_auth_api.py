def test_login_bad_password(client):
    r = client.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_roundtrip(client, admin_headers):
    r = client.get("/api/v1/auth/me", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "admin@test.local"
    assert body["role_name"] == "admin"


def test_refresh_flow(client):
    login = client.post("/api/v1/auth/login",
                        json={"email": "admin@test.local", "password": "Passw0rd!"}).json()
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_rbac_viewer_cannot_write(client, viewer_headers):
    r = client.post("/api/v1/clients", headers=viewer_headers,
                    json={"code": "X1", "name": "Nope"})
    assert r.status_code == 403
