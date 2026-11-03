# Hospital Appointment Booking System

A workflow-driven hospital appointment booking system built with **Camunda 8**. The BPMN workflow checks department slot availability using a **DMN decision table**, books an available slot, and sends appointment updates through a reusable Telegram notification process. It also handles full-slot rejection and appointment cancellation through a message event subprocess.

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Workflow (BPMN)](#workflow-bpmn)
- [DMN Decision Table](#dmn-decision-table)
- [Process Variables](#process-variables)
- [Telegram Notification Process](#telegram-notification-process)
- [Screenshots](#screenshots)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Automated Testing](#automated-testing)
- [Testing Scenarios](#testing-scenarios)
- [Troubleshooting](#troubleshooting)
- [Author](#author)

## Features

- Starts a hospital appointment booking process with patient and department details.
- Checks slot availability using a Camunda DMN decision table.
- Uses different capacity limits for Cardiology and other departments.
- Books the slot and sends a confirmation message when capacity is available.
- Sends a slot-full notification when the department has reached capacity.
- Handles cancellation messages correlated using the patient's ID.
- Releases the booked slot and sends a cancellation notification.
- Reuses a separate child process for Telegram notifications.
- Handles Telegram API errors using a BPMN boundary error event.
- Supports process monitoring and incident inspection through Camunda Operate.

## Tech Stack

| Layer | Technology |
|---|---|
| Workflow engine | Camunda 8 |
| Workflow modelling | BPMN 2.0 |
| Business decision | DMN decision table (`slot_decision`) |
| Notifications | Telegram Bot API |
| HTTP integration | Camunda REST Outbound Connector (`io.camunda:http-json:1`) |
| Automated tests | Python 3, `requests` |
| Monitoring | Camunda Operate |
| Modelling tool | Camunda Modeler 5.28.0 |

> The project contains the Camunda BPMN/DMN models and Python acceptance-test script. A separate web frontend or Spring Boot backend is not included.

## Architecture

| Component | Role |
|---|---|
| `hospital-booking-process` | Main process that manages booking, full-slot handling, and cancellation |
| `slot_decision` | DMN decision that returns the slot status and suggested action |
| `send-notification` | Reusable child process that sends Telegram messages |
| Telegram Bot API | Delivers confirmation, full-slot, and cancellation messages |
| Camunda Operate | Displays process instances, variables, execution paths, and incidents |
| `run_tests.py` | Deploys the models and runs the three acceptance-test scenarios |

The Python test script communicates with the Camunda REST API at `http://localhost:8080/v2`. The main BPMN process invokes the notification process through BPMN call activities. The notification process uses Camunda's HTTP JSON connector to call the Telegram Bot API.

## Workflow (BPMN)

Main process ID: `hospital-booking-process`

### 1. Appointment Booking

1. **Booking requested** starts the process.
2. **Check slot** evaluates the `slot_decision` DMN table.
3. **Slot available?** routes the process based on the returned `slotStatus`.
4. If the slot is `AVAILABLE`, **Book slot** creates the booking reference and marks the booking as confirmed.
5. **Send confirmation notification** calls the reusable `send-notification` process.
6. **Appointment scheduled** is reached and the booking waits for a cancellation message or continues to the booking-completed end event.

### 2. Slot-Full Path

1. If the DMN returns `FULL`, the process skips the booking task.
2. **Send slot full notification** calls the reusable notification process.
3. The process ends at **Booking rejected (slot full)** and the message offers an alternate slot or waiting list.

### 3. Cancellation Path

The main process contains an event subprocess named **Handle cancellation**.

1. It listens for the `AppointmentCancellation` message.
2. The message is correlated using `patientId`.
3. **Release slot** runs to release the appointment slot.
4. **Send cancellation notification** calls the reusable notification process.
5. The process ends at **Booking cancelled**.

The acceptance test checks that the scheduled task is cancelled when the cancellation event subprocess is triggered.

## DMN Decision Table

Decision ID: `slot_decision`

Hit policy: `UNIQUE`

The decision table uses `department` and `bookedCount` as inputs. It returns `slotStatus` and `suggestedAction`.

| Department | Booked count | Slot status | Suggested action |
|---|---|---|---|
| Cardiology | Less than 10 | `AVAILABLE` | Proceed to book slot |
| Cardiology | 10 or more | `FULL` | Offer alternate slot or waiting list |
| Other departments | Less than 15 | `AVAILABLE` | Proceed to book slot |
| Other departments | 15 or more | `FULL` | Offer alternate slot or waiting list |

The `UNIQUE` hit policy means only one rule should match a given input combination.

## Process Variables

The following variables are used by the main workflow and notification process.

| Variable | Purpose |
|---|---|
| `patientId` | Patient identifier; also used as the Telegram recipient/chat ID and cancellation correlation key |
| `patientName` | Patient name used in notification text |
| `department` | Department selected for the appointment |
| `preferredSlot` | Requested appointment time |
| `bookedCount` | Current booked count used by the DMN decision |
| `slotResult` | Result returned by the DMN decision |
| `slotStatus` | Availability result: `AVAILABLE` or `FULL` |
| `suggestedAction` | Action returned by the DMN table |
| `bookingReference` | Reference generated for a successful booking |
| `bookingStatus` | Booking state, such as `CONFIRMED` or `CANCELLED` |
| `recipientId` | Telegram chat ID passed to the notification child process |
| `messageText` | Text passed to the Telegram notification child process |
| `cancellationReason` | Reason supplied with the cancellation message |

## Telegram Notification Process

Child process ID: `send-notification`

The parent process calls this reusable process for confirmation, slot-full, and cancellation messages.

1. **Notification requested** starts the child process.
2. **Send Telegram Notification** uses the Camunda HTTP JSON connector.
3. The connector sends a `POST` request to the Telegram Bot API `sendMessage` endpoint.
4. The request body contains `chat_id` (`recipientId`) and `text` (`messageText`).
5. The connector is configured with three retries.
6. A boundary error event catches the `TELEGRAM_ERROR` BPMN error and routes to the notification process end event.

Configure the bot token as a Camunda secret named `TELEGRAM_BOT_TOKEN`. Do not commit the token to source control or place it directly in the BPMN file.

## Screenshots

### 1. Successful Booking and Cancellation Workflow

The Operate instance view shows the successful booking path and the cancellation event subprocess.

<img width="1920" height="912" alt="1_cancellation_path" src="https://github.com/user-attachments/assets/07991097-0c46-4b88-a69d-a16066fa0fa9" />


### 2. Slot-Full Path

The DMN decision routes a full department to the slot-full notification and booking-rejected end event.

<img width="1920" height="912" alt="3_slot_full_path" src="https://github.com/user-attachments/assets/18ec7860-a7e2-45ea-b4ff-312f401c2308" />


### 3. Reusable Telegram Notification Process

The child process sends a Telegram message and includes a boundary error event for handling Telegram API errors.

<img width="1920" height="912" alt="2_child_process_send_notification" src="https://github.com/user-attachments/assets/bc4e0d7d-0f53-4fdd-a363-c14dfa6eef53" />


### 4. Camunda Operate Dashboard

Operate provides an overview of process instances and incidents.

<img width="1437" height="682" alt="4_operate_dashboard" src="https://github.com/user-attachments/assets/a65224d6-31ef-4c92-b896-d784c91e07f0" />


### 5. Telegram Notification Output

Example Telegram messages for connection testing, appointment confirmation, cancellation, and slot-full handling.

<img width="589" height="1280" alt="WhatsApp Image 2026-11-03 at 11 19 03 AM" src="https://github.com/user-attachments/assets/8dd8c4cc-79bf-476a-a2a4-73b4b62fd3c2" />


## Project Structure

```text
hospital-appointment-booking/
├── hospital-booking-process.bpmn
├── send-notification.bpmn
├── slot_decision.dmn
├── run_tests.py
├── hospital-booking-readme-assets/
│   ├── booking-success.png
│   ├── slot-full.png
│   ├── send-notification-child-process.png
│   ├── camunda-operate-dashboard.png
│   └── telegram-notifications.png
└── README.md
```

## Getting Started

### Prerequisites

- Camunda 8 environment with the REST API available.
- Camunda Modeler (optional, for viewing or editing BPMN/DMN models).
- Python 3.
- Python package `requests`.
- A Telegram bot and the recipient's Telegram chat ID.
- A Camunda secret named `TELEGRAM_BOT_TOKEN`.

### 1. Start Camunda 8

Start your Camunda 8 environment and make sure the REST API is reachable at:

```text
http://localhost:8080/v2
```

If your Camunda REST API uses a different host or port, update `BASE_URL` in `run_tests.py`.

### 2. Configure the Telegram Bot Token

Create a Camunda secret with the name:

```text
TELEGRAM_BOT_TOKEN
```

The notification BPMN references this secret in the Telegram Bot API URL. Keep the actual token private.

### 3. Install the Python Dependency

From the project directory, run:

```bash
python -m pip install requests
```

### 4. Deploy and Run the Workflow Tests

Keep the BPMN files, DMN file, and `run_tests.py` in the same directory. Run:

```bash
python run_tests.py
```

The script deploys the three models to Camunda and executes the booking, slot-full, and cancellation scenarios.

> The test script currently contains a Telegram recipient/chat ID in the successful-booking and cancellation test cases. Replace that value with your own test chat ID before running the script. Use test data only.

## Automated Testing

The test script uses the Camunda REST API v2.

| Operation | Method | Endpoint |
|---|---|---|
| Deploy BPMN and DMN resources | `POST` | `/deployments` |
| Start a process instance | `POST` | `/process-instances` |
| Read a process instance | `GET` | `/process-instances/{processInstanceKey}` |
| Read element-instance statistics | `GET` | `/process-instances/{processInstanceKey}/statistics/element-instances` |
| Publish a cancellation message | `POST` | `/messages/publication` |

The script checks process state, incidents, completed or active BPMN elements, and the cancellation path.

## Testing Scenarios

| # | Scenario | Input | Expected Result |
|---|---|---|---|
| 1 | Successful booking | Cardiology, `bookedCount = 3` | DMN returns `AVAILABLE`; slot is booked; confirmation child process completes; scheduled task becomes active |
| 2 | Slot full | Cardiology, `bookedCount = 12` | DMN returns `FULL`; slot-full notification runs; booking-rejected end event is reached |
| 3 | Cancellation after booking | Cardiology, `bookedCount = 3`, then publish `AppointmentCancellation` | Cancellation event subprocess runs; scheduled task is cancelled; slot is released; cancellation notification runs |

To confirm execution, open Camunda Operate and inspect the process instance diagram, variables, and incident information.

## Troubleshooting

- **Process instance is not created:** Confirm Camunda is running and `BASE_URL` in `run_tests.py` points to the correct REST API.
- **Process is stuck at a service task:** Check that the HTTP JSON connector is available and that the connector task type is supported by your Camunda environment.
- **Telegram message is not delivered:** Verify the `TELEGRAM_BOT_TOKEN` secret, recipient chat ID, and that the Telegram bot can message the recipient.
- **Telegram API error:** Inspect the child process instance and Operate incidents. The BPMN boundary error event is configured to catch `TELEGRAM_ERROR`.
- **Deployment fails:** Confirm that all three model files are in the working directory and that the REST API accepts the deployment request.
- **Cancellation does not trigger:** Ensure the published message name is exactly `AppointmentCancellation` and its `correlationKey` matches the process variable `patientId`.
- **DMN returns an unexpected result:** Check the exact department string and numeric `bookedCount` input. Cardiology uses a limit of 10; other departments use a limit of 15.

## Author

**Ranjith Solomon**  
B.Tech Computer Science  
SRM Institute of Science and Technology
