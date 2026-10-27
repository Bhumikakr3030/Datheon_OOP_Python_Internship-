Datheon OOP & System Design Internship — Python Portfolio
A collection of Python projects completed as part of the Datheon Object-Oriented Programming (OOP) & System Design Internship. This repository demonstrates object-oriented design, SOLID principles, design patterns, and Low-Level Design (LLD).
Note: These are educational portfolio implementations. Integrations such as real payment processing, real email/SMS delivery, persistent banking ledgers, and live parking sensors are not configured unless explicitly stated in the individual project README files.

Internship Overview
- Program: Object-Oriented Programming (OOP) & System Design Internship
- Track: Computer Science & IT — Python & AI Applications
- Duration: 4 weeks (1 month)
- Level: Intermediate
- Focus areas: OOP fundamentals, SOLID principles, design patterns, modular architecture, UML, testing, and system design
- Registration: Advertised as free by the program listing
Projects
Task 1 — Multi-Currency Banking & Ledger Engine
Concepts: Abstraction, encapsulation, inheritance, polymorphism, validation, transaction history, and account-specific rules.
- Abstract Account base class.
- SavingsAccount, CheckingAccount, and HighYieldAccount.
- Monetary calculations using Decimal.
- Account-level currency support and transaction records.
- Unit tests and usage examples.
Project files: [`oop_banking_ledger_project/`](./oop_banking_ledger_project/)
Task 2 — SOLID Notification & Alert Dispatch Framework
Concepts: All five SOLID principles, interface abstractions, dependency injection, and extensibility.
- Email, SMS, Slack, and WhatsApp channel adapters.
- Pluggable NotificationChannel abstraction.
- Separate message formatting and logging components.
- Notification results and unit tests.
Project files: [`solid_notification_engine/`](./solid_notification_engine/)
Task 3 — E-Commerce Order Pipeline
Concepts: Singleton, Factory, and Observer design patterns.
- Process-local configuration Singleton.
- Payment handler factory for Credit Card, UPI, PayPal, and Crypto.
- Order status events for logistics, invoicing, and email listeners.
- Status transition validation and tests.
Project files: [`ecommerce_order_pipeline/`](./ecommerce_order_pipeline/)
Task 4 — Smart Parking Lot LLD
Concepts: Object-oriented low-level design, UML class diagrams, allocation algorithms, and test-driven validation.
- Multi-floor parking lot.
- Motorcycles, compact cars, large SUVs, and electric vehicles.
- Automated compatible-slot selection and EV charging-slot preference.
- Parking tickets, exit receipts, hourly rates, and configurable weekend multiplier.
- UML diagram and unit tests.
Project files: [`smart_parking_lld/`](./smart_parking_lld/)
Technology Stack
- Python 3.10+
- Python standard library
- Object-oriented programming and modular package design
- unittest for automated tests
- Mermaid for the UML class diagram
Run a Project
Open the relevant project folder in a terminal.

For projects that include main.py:
python main.py
Run tests from the project folder:
python -m unittest discover -s tests -v
See each project's README for its exact setup, architecture, assumptions, and limitations.
Repository Structure
Datheon_OOP_Python_Internship-/
├── README.md
├── banking_engine.py                 # Earlier standalone Task 1 version
├── notification_engine.py            # Earlier standalone Task 2 version
├── order_pipeline.py                 # Earlier standalone Task 3 version
├── oop_banking_ledger_project/
│   └── oop_banking_ledger/
├── solid_notification_engine/
│   └── solid_notification_engine/
├── ecommerce_order_pipeline/
│   └── ecommerce_order_pipeline/
└── smart_parking_lld/
    └── smart_parking_lld/
The folder nesting above reflects the current repository paths. You can simplify the layout later by moving each project's contents up one level inside its task folder and removing duplicate or obsolete standalone files.

Learning Outcomes
- Apply the four pillars of OOP to a financial domain.
- Build decoupled code using SOLID principles and dependency injection.
- Use common creational and behavioral design patterns.
- Design a multi-floor system with UML, allocation rules, and pricing logic.
- Document assumptions, run automated tests, and maintain a GitHub portfolio.
Disclaimer
This repository is a learning portfolio and is not intended for direct production use. Real financial, notification, payment, or parking deployments require security controls, reliable persistence, monitoring, provider integrations, and additional operational testing.
Author: Bhumikakr3030
Repository: Datheon_OOP_Python_Internship-
