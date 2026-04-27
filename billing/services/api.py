from datetime import date, timedelta


def get_invoices():
    today = date.today()
    return [
        {
            "id": "101",
            "status": "Unpaid",
            "duedate": str(today + timedelta(days=7)),
            "client_id": "1",
        },
        {
            "id": "102",
            "status": "Unpaid",
            "duedate": str(today + timedelta(days=1)),
            "client_id": "2",
        },
        {
            "id": "103",
            "status": "Unpaid",
            "duedate": str(today),
            "client_id": "3",
        },
        {
            "id": "104",
            "status": "Paid",
            "duedate": str(today),
            "client_id": "4",
        },
    ]

def get_invoice_details(invoice_id):
    mock_data = {
        "101": {
            "invoice": {
                "id": "101",
                "status": "Unpaid",
                "duedate": str(date.today()),
                "client": {
                    "email": "balajiselvam0201@gmail.com",
                    "firstname": "John",
                    "lastname": "Doe",
                },
                "items": [
                    {"description": "Hosting Plan - 1 Year"}
                ],
                "total": "100.00",
            }
        },
        "102": {
            "invoice": {
                "id": "102",
                "status": "Unpaid",
                "duedate": str(date.today()),
                "client": {
                    "email": "balajiselvam0201@gmail.com",
                    "firstname": "Alice",
                    "lastname": "Smith",
                },
                "items": [
                    {"description": "Domain Renewal"}
                ],
                "total": "50.00",
            }
        },
        "103": {
            "invoice": {
                "id": "103",
                "status": "Unpaid",
                "duedate": str(date.today()),
                "client": {
                    "email": "balajiselvam0201@gmail.com",
                    "firstname": "Bob",
                    "lastname": "Brown",
                },
                "items": [
                    {"description": "SSL Certificate"},
                ],
                "total": "20.00",
            }
        },
        "104": {
            "invoice": {
                "id": "103",
                "status": "Paid",
                "duedate": str(date.today()),
                "client": {
                    "email": "balajiselvam0201@gmail.com",
                    "firstname": "Unknown",
                    "lastname": "User",
                },
                "items": [
                    {"description": "SSL Certificate"},
                ],
                "total": "20.00",
            }
        },
    }

    return mock_data.get(invoice_id)