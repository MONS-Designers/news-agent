from fastapi.testclient import TestClient


def test_unauthenticated_gets_401(client: TestClient):
    response = client.get("/me/preferences")
    assert response.status_code == 401


def test_user_gets_all_topics_none_subscribed(as_user_with_db: TestClient):
    response = as_user_with_db.get("/me/preferences")
    assert response.status_code == 200
    body = response.json()
    assert {item["name"] for item in body} == {"AI", "Cybersecurity", "Space"}
    assert all(item["subscribed"] is False for item in body)


def test_put_then_get_reflects_new_subscriptions(as_user_with_db: TestClient):
    get_response = as_user_with_db.get("/me/preferences")
    ai_id = next(item["topic_id"] for item in get_response.json() if item["name"] == "AI")

    put_response = as_user_with_db.put("/me/preferences", json={"topic_ids": [ai_id]})
    assert put_response.status_code == 200
    put_body = {item["name"]: item["subscribed"] for item in put_response.json()}
    assert put_body == {"AI": True, "Cybersecurity": False, "Space": False}

    get_response = as_user_with_db.get("/me/preferences")
    get_body = {item["name"]: item["subscribed"] for item in get_response.json()}
    assert get_body == put_body


def test_put_unknown_topic_id_returns_400(as_user_with_db: TestClient):
    response = as_user_with_db.put("/me/preferences", json={"topic_ids": [999]})
    assert response.status_code == 400
