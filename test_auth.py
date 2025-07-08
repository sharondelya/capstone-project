import pytest
from unittest.mock import patch, MagicMock
from app import AuthManager
from werkzeug.security import generate_password_hash
# authentication testing
@patch('app.get_db_connection')
def test_login_user_client_success(mock_get_db_connection):
    """Tests successful login for a client."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    hashed_password = generate_password_hash('password123')
    mock_cursor.fetchone.return_value = {
        'userid': 1,
        'name': 'Test Client',
        'email': 'client@example.com',
        'password': hashed_password,
        'image': None,
        'is_banned': False
    }

    user = AuthManager.login_user('client@example.com', 'password123')
    assert user is not None
    assert user['user_type'] == 'client'
    assert user['name'] == 'Test Client'

@patch('app.get_db_connection')
def test_login_user_business_success(mock_get_db_connection):
    """Tests successful login for a business."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    # First fetchone is for client check (returns None)
    # Second fetchone is for business check
    hashed_password = generate_password_hash('password456')
    mock_cursor.fetchone.side_effect = [
        None,
        {
            'userid': 2,
            'name': 'Test Business',
            'email': 'business@example.com',
            'password': hashed_password,
            'image': None,
            'is_banned': False
        }
    ]

    user = AuthManager.login_user('business@example.com', 'password456')
    assert user is not None
    assert user['user_type'] == 'business'
    assert user['name'] == 'Test Business'

@patch('app.get_db_connection')
def test_login_user_wrong_password(mock_get_db_connection):
    """Tests login with an incorrect password."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    hashed_password = generate_password_hash('password123')
    mock_cursor.fetchone.return_value = {
        'userid': 1,
        'name': 'Test Client',
        'email': 'client@example.com',
        'password': hashed_password,
        'image': None,
        'is_banned': False
    }

    user = AuthManager.login_user('client@example.com', 'wrongpassword')
    assert user is None

@patch('app.get_db_connection')
def test_login_user_not_found(mock_get_db_connection):
    """Tests login with a non-existent email."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    # Both client and business checks return None
    mock_cursor.fetchone.return_value = None

    user = AuthManager.login_user('nouser@example.com', 'password123')
    assert user is None

@patch('app.get_db_connection')
def test_email_exists_true(mock_get_db_connection):
    """Tests if email_exists returns True for an existing email."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    mock_cursor.fetchone.return_value = ('client@example.com',)

    assert AuthManager.email_exists('client@example.com') is True

@patch('app.get_db_connection')
def test_email_exists_false(mock_get_db_connection):
    """Tests if email_exists returns False for a non-existent email."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    mock_cursor.fetchone.return_value = None

    assert AuthManager.email_exists('no-email@example.com') is False


@patch('app.get_db_connection')
def test_login_user_case_insensitive_email(mock_get_db_connection):
    """Tests that email is case-insensitive during login."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    hashed_password = generate_password_hash('password123')
    mock_cursor.fetchone.return_value = {
        'userid': 1,
        'name': 'Test Client',
        'email': 'client@example.com',
        'password': hashed_password,
        'image': None,
        'is_banned': False
    }

    user = AuthManager.login_user('CLIENT@example.com', 'password123')
    assert user is not None
    assert user['user_type'] == 'client'