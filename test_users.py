import pytest
from unittest.mock import patch, MagicMock
from app import Client, Business
# Users Role based Testing like CLient, Business and Admin
# Fixtures for common data
@pytest.fixture
def client_data():
    return {
        "name": "Test Client",
        "email": "client@example.com",
        "password": "Password123",
        "address": "123 Test St",
        "primary_location": "Ontario",
        "age": "30",
        "gender": "male"
    }

@pytest.fixture
def business_data():
    return {
        "name": "Test Owner",
        "email": "business@example.com",
        "password": "Password456",
        "address": "456 Business Ave",
        "primary_location": "Quebec",
        "business_name": "Test Business Inc.",
        "contact_info": "123-456-7890",
        "bank_account_number": "1234567890",
        "business_description": "A test business description.",
        "target_keywords": "testing,pytest,mocking"
    }

def test_client_creation(client_data):
    """Tests successful creation of a Client object."""
    client = Client(**client_data)
    assert client.name == client_data["name"]
    assert client.email == client_data["email"]
    assert client.get_user_type() == "client"

def test_business_creation(business_data):
    """Tests successful creation of a Business object."""
    business = Business(**business_data)
    assert business.business_name == business_data["business_name"]
    assert business.email == business_data["email"]
    assert business.get_user_type() == "business"

def test_client_validation_success(client_data):
    """Tests that a valid client passes validation."""
    client = Client(**client_data)
    errors = client.validate_fields()
    assert not errors

def test_client_validation_failure(client_data):
    """Tests that an invalid client fails validation."""
    client_data["name"] = "A" # Invalid name
    client = Client(**client_data)
    errors = client.validate_fields()
    assert "name" in errors

def test_business_validation_success(business_data):
    """Tests that a valid business passes validation."""
    business = Business(**business_data)
    errors = business.validate_fields()
    assert not errors

def test_business_validation_failure(business_data):
    """Tests that an invalid business fails validation."""
    business_data["contact_info"] = "12345" # Invalid contact
    business = Business(**business_data)
    errors = business.validate_fields()
    assert "contact_info" in errors

@patch('app.get_db_connection')
def test_client_save_to_database(mock_get_db_connection, client_data):
    """Tests the save_to_database method for a Client."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    client = Client(**client_data)
    result = client.save_to_database()

    assert result is True
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()

@patch('app.get_db_connection')
def test_business_save_to_database(mock_get_db_connection, business_data):
    """Tests the save_to_database method for a Business."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    business = Business(**business_data)
    result = business.save_to_database()

    assert result is True
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()
def test_client_invalid_email(client_data):
    """Tests client validation with an invalid email format."""
    client_data["email"] = "not-an-email"
    client = Client(**client_data)
    errors = client.validate_fields()
    assert "email" in errors

def test_business_invalid_phone(business_data):
    """Tests business validation with an invalid phone number."""
    business_data["contact_info"] = "123-456-789" # Invalid format
    business = Business(**business_data)
    errors = business.validate_fields()
    assert "contact_info" in errors

def test_business_invalid_account_number(business_data):
    """Tests business validation with an invalid bank account number."""
    business_data["bank_account_number"] = "12345" # Too short
    business = Business(**business_data)
    errors = business.validate_fields()
    assert "bank_account_number" in errors

def test_business_invalid_keywords(business_data):
    """Tests business validation with an incorrect number of keywords."""
    business_data["target_keywords"] = "one" # Not enough keywords
    business = Business(**business_data)
    errors = business.validate_fields()
    assert "target_keywords" in errors

    business_data["target_keywords"] = "one,two,three,four,five,six" # Too many
    business = Business(**business_data)
    errors = business.validate_fields()
    assert "target_keywords" in errors