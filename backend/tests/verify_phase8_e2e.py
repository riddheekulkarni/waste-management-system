import io
import requests
from PIL import Image

BASE_URL = "http://127.0.0.1:5050"

def main():
    print("=== Phase 8 End-to-End Live HTTP Journey ===")
    
    # 1. Login as Admin
    admin_session = requests.Session()
    login_adm = admin_session.post(f"{BASE_URL}/api/auth/login", json={
        "identifier": "admin",
        "password": "admin123"
    })
    print(f"Admin login: status {login_adm.status_code}")
    assert login_adm.status_code == 200

    # 2. Login as Citizen
    citizen_session = requests.Session()
    login_cit = citizen_session.post(f"{BASE_URL}/api/auth/login", json={
        "identifier": "citizen",
        "password": "citizen123"
    })
    print(f"Citizen login: status {login_cit.status_code}")
    assert login_cit.status_code == 200

    # 3. Get existing complaint
    # Admin or Citizen can list complaints
    complaints_res = citizen_session.get(f"{BASE_URL}/api/complaints?per_page=10")
    print(f"Get complaints: status {complaints_res.status_code}")
    assert complaints_res.status_code == 200
    complaints = complaints_res.json().get("items", [])
    assert len(complaints) > 0
    # Find an active complaint that can be transitioned to IN_PROGRESS
    active_items = [c for c in complaints if c.get("status") in ("IN_PROGRESS", "ASSIGNED", "VERIFIED")]
    if not active_items:
        # Fallback to any item
        active_items = complaints
    target = active_items[0]
    ticket_id = target["ticket_id"]
    print(f"Selected Ticket ID: {ticket_id}, Current Status: {target['status']}")

    # 4. Admin moves ticket to IN_PROGRESS (if not already)
    if target["status"] != "IN_PROGRESS":
        status_res = admin_session.patch(f"{BASE_URL}/api/complaints/{ticket_id}/status", json={
            "status": "IN_PROGRESS",
            "department": "Sanitation Department"
        })
        print(f"Admin update status to IN_PROGRESS: status {status_res.status_code}")
        assert status_res.status_code == 200
    else:
        print("Ticket is already IN_PROGRESS, proceeding to resolution submission.")

    # 5. Admin submits resolution evidence
    res_buf = io.BytesIO()
    Image.new("RGB", (100, 100), color="green").save(res_buf, format="JPEG")
    res_buf.seek(0)
    
    resolution_res = admin_session.post(
        f"{BASE_URL}/api/complaints/{ticket_id}/resolution",
        data={"note": "Field crew cleared 200kg of waste and pressure-washed the sidewalk."},
        files={"image": ("clean_sidewalk.jpg", res_buf, "image/jpeg")}
    )
    print(f"Admin submit resolution: status {resolution_res.status_code}")
    assert resolution_res.status_code == 200
    res_data = resolution_res.json()
    assert res_data["complaint"]["status"] == "RESOLUTION_SUBMITTED"
    print(f"Resolution submitted successfully! Status: {res_data['complaint']['status']}")

    # 6. Citizen views resolution
    view_res = citizen_session.get(f"{BASE_URL}/api/complaints/{ticket_id}/resolution")
    print(f"Citizen view resolution: status {view_res.status_code}")
    assert view_res.status_code == 200
    print(f"Resolution note seen by citizen: '{view_res.json()['resolution_note']}'")

    # 7. Citizen submits feedback: CONFIRMED
    feedback_res = citizen_session.post(
        f"{BASE_URL}/api/complaints/{ticket_id}/feedback",
        json={
            "result": "CONFIRMED",
            "comment": "Site looks completely spotless now. Great job!"
        }
    )
    print(f"Citizen submit feedback: status {feedback_res.status_code}")
    assert feedback_res.status_code == 201
    fb_data = feedback_res.json()
    assert fb_data["complaint"]["status"] == "RESOLVED"
    print(f"Complaint successfully transitioned to: {fb_data['complaint']['status']}")

    # 8. Admin views Citizen Feedback Queue
    admin_fb_queue = admin_session.get(f"{BASE_URL}/api/admin/feedback")
    print(f"Admin view feedback queue: status {admin_fb_queue.status_code}")
    assert admin_fb_queue.status_code == 200
    feedbacks = admin_fb_queue.json()["feedback"]
    matched = [f for f in feedbacks if f["complaint_id"] == ticket_id]
    assert len(matched) > 0
    print(f"Matched feedback in admin queue: Ticket #{matched[0]['complaint_id']}, Result: {matched[0]['result']}, Comment: '{matched[0]['comment']}'")

    # 9. Admin views Insights (field operations metrics)
    insights_res = admin_session.get(f"{BASE_URL}/api/admin/insights?days=7")
    print(f"Admin insights: status {insights_res.status_code}")
    assert insights_res.status_code == 200
    field_ops = insights_res.json().get("field_operations", {})
    print(f"Field Operations Insights: {field_ops}")
    assert field_ops["total_resolution_submissions"] >= 1
    assert field_ops["citizen_confirmations"] >= 1

    print("\n[SUCCESS] End-to-End Live HTTP Journey Passed Perfectly!")

if __name__ == "__main__":
    main()
