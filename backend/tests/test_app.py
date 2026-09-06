import io
import json
from PIL import Image


def create_dummy_image_bytes():
    img = Image.new("RGB", (100, 100), color="red")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)
    return img_byte_arr


def test_auth_register_and_login(client):
    # Register new citizen
    res = client.post("/api/auth/register", json={
        "username": "newuser",
        "email": "newuser@test.com",
        "password": "password123",
        "role": "citizen"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["user"]["username"] == "newuser"

    # Current user /me
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.get_json()["user"]["username"] == "newuser"

    # Logout
    client.post("/api/auth/logout")
    me_res2 = client.get("/api/auth/me")
    assert me_res2.get_json()["user"] is None

    # Login
    login_res = client.post("/api/auth/login", json={
        "identifier": "newuser",
        "password": "password123"
    })
    assert login_res.status_code == 200
    assert login_res.get_json()["user"]["username"] == "newuser"


def test_invalid_image_upload(client):
    data = {
        "image": (io.BytesIO(b"not an image file content"), "test.txt")
    }
    res = client.post("/api/complaints/upload", data=data, content_type="multipart/form-data")
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_valid_complaint_upload_and_duplicate_detection(client):
    img_bytes = create_dummy_image_bytes()
    data = {
        "image": (img_bytes, "test_waste.jpg"),
        "latitude": 18.5204,
        "longitude": 73.8567,
        "address": "Central Pune Street"
    }

    res1 = client.post("/api/complaints/upload", data=data, content_type="multipart/form-data")
    assert res1.status_code == 201
    ticket1 = res1.get_json()
    assert ticket1["is_duplicate"] is False
    ticket1_id = ticket1["ticket_id"]

    # Check duplicate endpoint
    check_res = client.post("/api/complaints/check-duplicate", json={
        "latitude": 18.52041,
        "longitude": 73.85671
    })
    assert check_res.status_code == 200
    assert check_res.get_json()["is_duplicate"] is True

    # Upload second complaint at almost exact location -> should be marked duplicate
    img_bytes2 = create_dummy_image_bytes()
    data2 = {
        "image": (img_bytes2, "test_waste_near.jpg"),
        "latitude": 18.52041,
        "longitude": 73.85671,
        "address": "Central Pune Street (Near)"
    }
    res2 = client.post("/api/complaints/upload", data=data2, content_type="multipart/form-data")
    assert res2.status_code == 201
    ticket2 = res2.get_json()
    assert ticket2["is_duplicate"] is True
    assert ticket2["duplicate_of_id"] == ticket1_id


def test_admin_rbac_and_status_update(client):
    # Citizen login
    client.post("/api/auth/login", json={
        "identifier": "testcitizen",
        "password": "citizenpass"
    })

    # Summary analytics should fail for non-admin
    res_analytics = client.get("/api/analytics/summary")
    assert res_analytics.status_code == 403

    # Admin login
    client.post("/api/auth/login", json={
        "identifier": "testadmin",
        "password": "adminpass"
    })

    # Summary analytics should work for admin
    res_admin_summary = client.get("/api/analytics/summary")
    assert res_admin_summary.status_code == 200
    summary_data = res_admin_summary.get_json()
    assert "total_complaints" in summary_data

    # Geo analytics endpoint
    res_geo = client.get("/api/analytics/geo")
    assert res_geo.status_code == 200
    assert "points" in res_geo.get_json()
