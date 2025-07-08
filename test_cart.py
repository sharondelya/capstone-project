import pytest
from unittest.mock import patch, MagicMock
from app import CartManager
from decimal import Decimal
# Cart Testing
@pytest.fixture
def cart_manager():
    return CartManager()

@patch('app.get_db_connection')
def test_get_or_create_cart_existing(mock_get_db_connection, cart_manager):
    """Tests retrieving an existing active cart."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (101,) # Existing cart_id

    cart_id = cart_manager.get_or_create_cart(1)
    assert cart_id == 101

@patch('app.get_db_connection')
def test_get_or_create_cart_new(mock_get_db_connection, cart_manager):
    """Tests creating a new cart when no active one exists."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    # First fetchone returns None (no active cart), second returns new cart_id
    mock_cursor.fetchone.side_effect = [None, (102,)]

    cart_id = cart_manager.get_or_create_cart(1)
    assert cart_id == 102
    mock_conn.commit.assert_called_once()

@patch('app.CartManager._get_item_details')
@patch('app.CartManager.get_or_create_cart')
@patch('app.get_db_connection')
def test_add_to_cart_new_item(mock_get_db_connection, mock_get_or_create_cart, mock_get_item_details, cart_manager):
    """Tests adding a new item to the cart."""
    mock_get_item_details.return_value = {'item_price': '10.00', 'quantityinstock': 5, 'businessid': 1}
    mock_get_or_create_cart.return_value = 101
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None # Item not in cart

    result = cart_manager.add_to_cart(1, 1, 'chemical', 2)
    assert result['success'] is True
    mock_cursor.execute.call_count == 2 # Once to check, once to insert
    mock_conn.commit.assert_called_once()

@patch('app.CartManager._get_item_details')
@patch('app.CartManager.get_or_create_cart')
@patch('app.get_db_connection')
def test_add_to_cart_existing_item(mock_get_db_connection, mock_get_or_create_cart, mock_get_item_details, cart_manager):
    """Tests adding an item that already exists in the cart."""
    mock_get_item_details.return_value = {'item_price': '10.00', 'quantityinstock': 5, 'businessid': 1}
    mock_get_or_create_cart.return_value = 101
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (1, 1) # cart_item_id, quantity

    result = cart_manager.add_to_cart(1, 1, 'chemical', 1)
    assert result['success'] is True
    # Check that UPDATE was called
    assert 'UPDATE cart_items' in mock_cursor.execute.call_args[0][0]
    mock_conn.commit.assert_called_once()

@patch('app.CartManager._get_item_details')
def test_add_to_cart_insufficient_stock(mock_get_item_details, cart_manager):
    """Tests adding an item with insufficient stock."""
    mock_get_item_details.return_value = {'item_price': '10.00', 'quantityinstock': 1, 'businessid': 1}

    result = cart_manager.add_to_cart(1, 1, 'chemical', 2)
    assert result['success'] is False
    assert 'Only 1 units available' in result['message']

@patch('app.CartManager.get_or_create_cart')
@patch('app.get_db_connection')
def test_remove_from_cart(mock_get_db_connection, mock_get_or_create_cart, cart_manager):
    """Tests removing an item from the cart."""
    mock_get_or_create_cart.return_value = 101
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    result = cart_manager.remove_from_cart(1, 1)
    assert result is True
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()

@patch('app.CartManager.get_or_create_cart')
@patch('app.get_db_connection')
def test_get_cart_details(mock_get_db_connection, mock_get_or_create_cart, cart_manager):
    """Tests the get_cart_details method."""
    mock_get_or_create_cart.return_value = 101
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = [
        (1, 1, 'chemical', 2, Decimal('10.00'), Decimal('20.00'), 1, 'Chem A', b'img', 'Biz A'),
        (2, 2, 'machinery', 1, Decimal('50.00'), Decimal('50.00'), 1, 'Mach B', b'img', 'Biz A')
    ]

    cart_details = cart_manager.get_cart_details(1)
    assert cart_details['total_amount'] == 70.0
    assert cart_details['commission'] == 7.0
    assert cart_details['final_total'] == 77.0
    assert len(cart_details['cart_items']) == 2