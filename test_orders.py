import pytest
from unittest.mock import patch, MagicMock
from app import OrderManager, PaymentManager
from decimal import Decimal
# Order Placement Testing
@pytest.fixture
def order_manager():
    return OrderManager()

@pytest.fixture
def payment_manager():
    return PaymentManager()

@pytest.fixture
def cart_details():
    return {
        'cart_id': 101,
        'total_amount': '100.00',
        'commission': '10.00',
        'final_total': '110.00',
        'cart_items': [{'itemid': 1}] # Dummy item
    }

@patch('app.get_db_connection')
def test_create_order_success(mock_get_db_connection, order_manager, cart_details):
    """Tests successful creation of an order."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (201,) # New order_id

    order_id = order_manager.create_order(1, "123 Main St", cart_details)
    assert order_id == 201
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()

@patch('app.get_db_connection')
def test_update_payment_status(mock_get_db_connection, order_manager):
    """Tests updating the payment status of an order."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    result = order_manager.update_payment_status(201, 'pi_123', 'completed')
    assert result is True
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()

@patch('stripe.PaymentIntent.create')
def test_create_payment_intent_success(mock_stripe_create, payment_manager):
    """Tests successful creation of a Stripe PaymentIntent."""
    mock_intent = MagicMock()
    mock_intent.client_secret = 'cs_123'
    mock_intent.id = 'pi_123'
    mock_stripe_create.return_value = mock_intent

    result = payment_manager.create_payment_intent(110.00, order_id=201)
    assert result['success'] is True
    assert result['client_secret'] == 'cs_123'
    mock_stripe_create.assert_called_once_with(
        amount=11000,
        currency='usd',
        metadata={'order_id': 201}
    )

@patch('stripe.PaymentIntent.create')
def test_create_payment_intent_stripe_error(mock_stripe_create, payment_manager):
    """Tests handling of a Stripe error during PaymentIntent creation."""
    mock_stripe_create.side_effect = Exception("Stripe Error")

    result = payment_manager.create_payment_intent(110.00, order_id=201)
    assert result['success'] is False
    assert 'error' in result