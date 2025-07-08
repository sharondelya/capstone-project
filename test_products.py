import pytest
from unittest.mock import patch, MagicMock
from app import Machine, Chemical, Service
from datetime import date, timedelta
# Products feature Testing
# Fixtures for common data
@pytest.fixture
def machine_data():
    return {
        "name": "Test Machine",
        "price": 1000.0,
        "description": "A machine for testing purposes.",
        "machine_type": "Tractor",
        "dimensions": ["10", "5", "3"],
        "weight": 500.0,
        "power_source": "Diesel",
        "warranty": 2,
        "quantity": 5,
        "image_data": b"fake_image_data",
        "business_id": 1
    }

@pytest.fixture
def chemical_data():
    return {
        "name": "Test Chemical",
        "price": 50.0,
        "description": "A chemical for testing.",
        "chemical_type": "Pesticide",
        "metric_system": "Liters",
        "expiry_date": (date.today() + timedelta(days=365)).strftime('%Y-%m-%d'),
        "quantity": 10.5,
        "hazard_level": 3.0,
        "stock_quantity": 100,
        "image_data": b"fake_image_data",
        "business_id": 1
    }

@pytest.fixture
def service_data():
    return {
        "name": "Test Service",
        "price": 200.0,
        "description": "A service for testing.",
        "service_type": "Consulting",
        "availability": "true",
        "base_charges": 150.0,
        "image_data": b"fake_image_data",
        "business_id": 1
    }

def test_machine_creation(machine_data):
    """Tests successful creation of a Machine object."""
    machine = Machine(**machine_data)
    assert machine.name == machine_data["name"]
    assert machine.price == machine_data["price"]

def test_chemical_creation(chemical_data):
    """Tests successful creation of a Chemical object."""
    chemical = Chemical(**chemical_data)
    assert chemical.name == chemical_data["name"]
    assert chemical.expiry_date == chemical_data["expiry_date"]

def test_service_creation(service_data):
    """Tests successful creation of a Service object."""
    service = Service(**service_data)
    assert service.name == service_data["name"]
    assert service.availability is True

def test_machine_validation_success(machine_data):
    """Tests that a valid machine passes validation."""
    machine = Machine(**machine_data)
    errors = machine.validate_fields()
    assert not errors

def test_machine_validation_failure(machine_data):
    """Tests that an invalid machine fails validation."""
    machine_data["price"] = -100
    machine = Machine(**machine_data)
    errors = machine.validate_fields()
    assert "Price cannot be negative" in errors

def test_chemical_validation_success(chemical_data):
    """Tests that a valid chemical passes validation."""
    chemical = Chemical(**chemical_data)
    errors = chemical.validate_fields()
    assert not errors

def test_chemical_validation_failure(chemical_data):
    """Tests that an invalid chemical fails validation."""
    chemical_data["expiry_date"] = "2020-01-01" # Past date
    chemical = Chemical(**chemical_data)
    errors = chemical.validate_fields()
    assert "Expiry date must be in the future" in errors

def test_service_validation_success(service_data):
    """Tests that a valid service passes validation."""
    service = Service(**service_data)
    errors = service.validate_fields()
    assert not errors

def test_service_validation_failure(service_data):
    """Tests that an invalid service fails validation."""
    service_data["description"] = "short" # Too short
    service = Service(**service_data)
    errors = service.validate_fields()
    assert "Description must be at least 10 characters long" in errors

@patch('app.get_db_connection')
def test_machine_save_to_database(mock_get_db_connection, machine_data):
    """Tests the save_to_database method for a Machine."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (1,) # Mock returning an itemid

    machine = Machine(**machine_data)
    item_id = machine.save_to_database()

    assert item_id == 1
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()

@patch('app.get_db_connection')
def test_chemical_save_to_database(mock_get_db_connection, chemical_data):
    """Tests the save_to_database method for a Chemical."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (2,) # Mock returning an itemid

    chemical = Chemical(**chemical_data)
    item_id = chemical.save_to_database()

    assert item_id == 2
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()

@patch('app.get_db_connection')
def test_service_save_to_database(mock_get_db_connection, service_data):
    """Tests the save_to_database method for a Service."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (3,) # Mock returning an itemid

    service = Service(**service_data)
    item_id = service.save_to_database()

    assert item_id == 3
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()