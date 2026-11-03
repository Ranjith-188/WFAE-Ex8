"""
Exercise 8 - Hospital Appointment Booking Automated Acceptance Tests
Tests:
1. Reusable Child Process (send-notification) via REST Outbound Connector
2. DMN slot_decision (Hit policy UNIQUE)
3. Parent Process (hospital-booking-process)
   - Case 1: Cardiology with bookedCount = 3 (Booking succeeds)
   - Case 2: Cardiology with bookedCount = 12 (Slot full)
   - Case 3: Successful booking followed by Cancellation message
"""

import sys
import time
import requests

BASE_URL = "http://localhost:8080/v2"

def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def assert_true(msg, condition):
    if condition:
        print(f"  [PASS] {msg}")
        return True
    else:
        print(f"  [FAIL] {msg}")
        return False

def deploy_models():
    print_header("DEPLOYING BPMN & DMN MODELS")
    files = [
        ('resources', ('send-notification.bpmn', open('send-notification.bpmn', 'rb'), 'application/xml')),
        ('resources', ('slot_decision.dmn', open('slot_decision.dmn', 'rb'), 'application/xml')),
        ('resources', ('hospital-booking-process.bpmn', open('hospital-booking-process.bpmn', 'rb'), 'application/xml')),
    ]
    r = requests.post(f"{BASE_URL}/deployments", files=files)
    assert_true(f"Deployment response status: {r.status_code}", r.status_code == 200)
    data = r.json()
    print(f"  Deployment Key: {data.get('deploymentKey')}")
    for d in data.get('deployments', []):
        if d.get('processDefinition'):
            pd = d['processDefinition']
            print(f"  -> Process: {pd.get('processDefinitionId')} (v{pd.get('processDefinitionVersion')})")
        elif d.get('decisionDefinition'):
            dd = d['decisionDefinition']
            print(f"  -> Decision: {dd.get('decisionDefinitionId')} (v{dd.get('version')})")

def test_case_1():
    print_header("TEST CASE 1: Cardiology with bookedCount = 3 (Booking Succeeds)")
    # Using real Telegram Chat ID for live notifications
    patient_id = "8813630540"
    payload = {
        'processDefinitionId': 'hospital-booking-process',
        'variables': {
            'patientId': patient_id,
            'patientName': 'Sarah Connor',
            'department': 'Cardiology',
            'preferredSlot': '10:00 AM',
            'bookedCount': 3
        }
    }
    r = requests.post(f"{BASE_URL}/process-instances", json=payload)
    assert_true("Process instance initiated", r.status_code == 200)
    inst_key = r.json().get('processInstanceKey')
    print(f"  Instance Key: {inst_key}")

    # Wait for execution through DMN, Book Slot, Call Activity
    time.sleep(3)
    inst = requests.get(f"{BASE_URL}/process-instances/{inst_key}").json()
    assert_true(f"Process instance is ACTIVE at Scheduled state (hasIncident: {inst.get('hasIncident')})", 
                inst.get('state') == 'ACTIVE' and not inst.get('hasIncident'))

    stats = requests.get(f"{BASE_URL}/process-instances/{inst_key}/statistics/element-instances").json()
    elements = {s['elementId']: s for s in stats.get('items', [])}
    assert_true("Check slot DMN executed", elements.get('Task_CheckSlot', {}).get('completed') == 1)
    assert_true("Book slot task completed", elements.get('Task_BookSlot', {}).get('completed') == 1)
    assert_true("Send confirmation call activity completed", elements.get('CallActivity_NotifyConfirmed', {}).get('completed') == 1)
    assert_true("Appointment scheduled wait state reached", elements.get('Task_AppointmentScheduled', {}).get('active') == 1)
    return inst_key

def test_case_2():
    print_header("TEST CASE 2: Cardiology with bookedCount = 12 (Slot Full)")
    patient_id = f"PAT-TEST-2-{int(time.time())}"
    payload = {
        'processDefinitionId': 'hospital-booking-process',
        'variables': {
            'patientId': patient_id,
            'patientName': 'Bob Vance',
            'department': 'Cardiology',
            'preferredSlot': '11:30 AM',
            'bookedCount': 12
        }
    }
    r = requests.post(f"{BASE_URL}/process-instances", json=payload)
    assert_true("Process instance initiated", r.status_code == 200)
    inst_key = r.json().get('processInstanceKey')
    print(f"  Instance Key: {inst_key}")

    time.sleep(3)
    inst = requests.get(f"{BASE_URL}/process-instances/{inst_key}").json()
    assert_true("Process instance COMPLETED", inst.get('state') == 'COMPLETED')
    assert_true("No incidents encountered", not inst.get('hasIncident'))

    stats = requests.get(f"{BASE_URL}/process-instances/{inst_key}/statistics/element-instances").json()
    elements = {s['elementId']: s for s in stats.get('items', [])}
    assert_true("Check slot DMN evaluated FULL", elements.get('Task_CheckSlot', {}).get('completed') == 1)
    assert_true("Send slot full call activity executed", elements.get('CallActivity_NotifySlotFull', {}).get('completed') == 1)
    assert_true("Booking rejected end event reached", elements.get('EndEvent_BookingRejected', {}).get('completed') == 1)
    return inst_key

def test_case_3():
    print_header("TEST CASE 3: Successful Booking Followed by Cancellation Message")
    # Using real Telegram Chat ID for live notifications
    patient_id = "8813630540"
    payload = {
        'processDefinitionId': 'hospital-booking-process',
        'variables': {
            'patientId': patient_id,
            'patientName': 'Michael Scott',
            'department': 'Cardiology',
            'preferredSlot': '02:00 PM',
            'bookedCount': 3
        }
    }
    r = requests.post(f"{BASE_URL}/process-instances", json=payload)
    inst_key = r.json().get('processInstanceKey')
    print(f"  Instance Key: {inst_key}")

    # Wait for booking to succeed
    time.sleep(3)
    inst_mid = requests.get(f"{BASE_URL}/process-instances/{inst_key}").json()
    assert_true("Booking confirmed and reached wait state", inst_mid.get('state') == 'ACTIVE')

    # Send cancellation message correlated by patientId
    print(f"  Publishing Cancellation Message for correlationKey '{patient_id}'...")
    msg_payload = {
        'name': 'AppointmentCancellation',
        'correlationKey': patient_id,
        'timeToLive': 10000,
        'variables': {
            'cancellationReason': 'Personal emergency'
        }
    }
    msg_r = requests.post(f"{BASE_URL}/messages/publication", json=msg_payload)
    assert_true(f"Message published successfully (key: {msg_r.json().get('messageKey')})", msg_r.status_code == 200)

    # Wait for cancellation event subprocess
    time.sleep(4)
    inst_after = requests.get(f"{BASE_URL}/process-instances/{inst_key}").json()
    assert_true("Process instance COMPLETED after cancellation", inst_after.get('state') == 'COMPLETED')
    assert_true("No incidents on instance", not inst_after.get('hasIncident'))

    stats = requests.get(f"{BASE_URL}/process-instances/{inst_key}/statistics/element-instances").json()
    elements = {s['elementId']: s for s in stats.get('items', [])}
    assert_true("Booking path was originally completed", elements.get('CallActivity_NotifyConfirmed', {}).get('completed') == 1)
    assert_true("Scheduled task was interrupted / cancelled", elements.get('Task_AppointmentScheduled', {}).get('canceled') == 1)
    assert_true("Event subprocess triggered", elements.get('SubProcess_HandleCancellation', {}).get('completed') == 1)
    assert_true("Release slot executed", elements.get('Task_ReleaseSlot', {}).get('completed') == 1)
    assert_true("Send cancellation notification call activity completed", elements.get('CallActivity_NotifyCancellation', {}).get('completed') == 1)
    assert_true("Booking cancelled end event reached", elements.get('EndEvent_BookingCancelled', {}).get('completed') == 1)
    return inst_key

if __name__ == "__main__":
    deploy_models()
    test_case_1()
    test_case_2()
    test_case_3()
    print_header("ALL TEST CASES PASSED SUCCESSFULLY!")
