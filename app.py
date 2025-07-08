import random
import bcrypt
from flask import Flask, Response, render_template, request, redirect, url_for, flash, session, jsonify, make_response
import stripe
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import psycopg2
import pandas as pd
from io import BytesIO
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime, timedelta
import re
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import uuid
import base64
from datetime import datetime, date
from decimal import Decimal
import json


app = Flask(__name__)
app.config['SECRET_KEY'] = 'honeybee_secret'
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB max file size
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'honeybee:'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True if using HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
# Debug mode
app.config['DEBUG'] = os.environ.get('DEBUG', 'False').lower() == 'true'
# Database configuration
DB_CONFIG = {
    'host': 'pg-14c2d863-ijazabdullah127-f508.c.aivencloud.com',
    'port': 11068,
    'database': 'defaultdb',
    'user': 'avnadmin',
    'password': 'AVNS_Tjku63uorJ5CV1cKt_2',
    'sslmode': 'require'
}
app.config['STRIPE_PUBLISHABLE_KEY'] = 'pk_test_51RevekCj3fOXvb2I0VOCpL25hUjPxoPDRqWOdosK2soHpL9P8cWGVhmW8lNrMeBbvF4Cif5L5IIGUEug6Kzoks0O00zD2bp9K1'
app.config['STRIPE_SECRET_KEY'] = 'sk_test_51RevekCj3fOXvb2It1em8CgIX4L6nx0u4D5Tz0gZB3klCc1ciWisbYHGyyDmjQSXXlt7GYTEknhZGc3BHbd3ZD1400iPoHR5yw'

# Update the Stripe configuration in PaymentManager

stripe.api_key = 'sk_test_51RevekCj3fOXvb2It1em8CgIX4L6nx0u4D5Tz0gZB3klCc1ciWisbYHGyyDmjQSXXlt7GYTEknhZGc3BHbd3ZD1400iPoHR5yw'

class CartManager:
    """Manages cart operations with proper encapsulation"""
   
    def __init__(self):
        self.commission_rate = Decimal('0.10')  # 10% commission
    
    def get_or_create_cart(self, user_id: int) -> int:
        """Get active cart for user or create new one"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check for active cart
            cursor.execute("""
                SELECT cartid FROM cart 
                WHERE userid = %s AND is_active = true 
                ORDER BY created_at DESC LIMIT 1
            """, (user_id,))
            
            cart = cursor.fetchone()
            
            if cart:
                cart_id = cart[0]
            else:
                # Create new cart
                cursor.execute("""
                    INSERT INTO cart (userid, is_active) 
                    VALUES (%s, true) RETURNING cartid
                """, (user_id,))
                cart_id = cursor.fetchone()[0]
                conn.commit()
            
            cursor.close()
            conn.close()
            return cart_id
            
        except Exception as e:
            print(f"Error in get_or_create_cart: {e}")
            return None
    
    def add_to_cart(self, user_id: int, item_id: int, item_type: str, quantity: int) -> Dict:
        """Add item to cart with quantity validation"""
        try:
            # Validate item type
            if item_type not in ['chemical', 'machinery', 'service']:
                return {'success': False, 'message': 'Invalid item type'}
            
            # Get item details and check availability
            item_details = self._get_item_details(item_id, item_type)
            if not item_details:
                return {'success': False, 'message': 'Item not found'}
            
            # Check quantity availability (not applicable for services)
            if item_type != 'service' and quantity > item_details['quantityinstock']:
                return {'success': False, 'message': f'Only {item_details["quantityinstock"]} units available'}
            
            cart_id = self.get_or_create_cart(user_id)
            if not cart_id:
                return {'success': False, 'message': 'Error creating cart'}
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check if item already exists in cart
            cursor.execute("""
                SELECT cart_item_id, quantity FROM cart_items 
                WHERE cartid = %s AND itemid = %s AND itemtype = %s
            """, (cart_id, item_id, item_type))
            
            existing_item = cursor.fetchone()
            unit_price = Decimal(str(item_details['item_price']))
            
            if existing_item:
                # Update existing item
                new_quantity = existing_item[1] + quantity
                
                # Check total quantity doesn't exceed stock (except for services)
                if item_type != 'service' and new_quantity > item_details['quantityinstock']:
                    cursor.close()
                    conn.close()
                    return {'success': False, 'message': f'Total quantity would exceed available stock ({item_details["quantityinstock"]} units)'}
                
                total_price = unit_price * new_quantity
                cursor.execute("""
                    UPDATE cart_items 
                    SET quantity = %s, total_price = %s 
                    WHERE cart_item_id = %s
                """, (new_quantity, total_price, existing_item[0]))
            else:
                # Add new item
                total_price = unit_price * quantity
                cursor.execute("""
                    INSERT INTO cart_items (cartid, itemid, itemtype, quantity, unit_price, total_price, businessid)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (cart_id, item_id, item_type, quantity, unit_price, total_price, item_details['businessid']))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return {'success': True, 'message': 'Item added to cart successfully'}
            
        except Exception as e:
            print(f"Error adding to cart: {e}")
            return {'success': False, 'message': 'Error adding item to cart'}
    
    def _get_item_details(self, item_id: int, item_type: str) -> Optional[Dict]:
        """Get item details from appropriate table"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if item_type == 'chemical':
                cursor.execute("""
                    SELECT itemname, item_price, quantityinstock, businessid 
                    FROM chemical WHERE itemid = %s AND isdeleted = 0
                """, (item_id,))
            elif item_type == 'machinery':
                cursor.execute("""
                    SELECT itemname, item_price, quantityinstock, businessid 
                    FROM machinery WHERE itemid = %s AND isdeleted = 0
                """, (item_id,))
            elif item_type == 'service':
                cursor.execute("""
                    SELECT itemname, item_price, 999 as quantityinstock, businessid 
                    FROM service WHERE itemid = %s AND isdeleted = 0
                """, (item_id,))
            
            item = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if item:
                return {
                    'itemname': item[0],
                    'item_price': item[1],
                    'quantityinstock': item[2],
                    'businessid': item[3]
                }
            return None
            
        except Exception as e:
            print(f"Error getting item details: {e}")
            return None
    
    def get_cart_details(self, user_id: int) -> Dict:
        """Get complete cart details for user including services"""
        try:
            cart_id = self.get_or_create_cart(user_id)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get all cart items including services
            cursor.execute("""
                SELECT ci.cart_item_id, ci.itemid, ci.itemtype, ci.quantity, 
                       ci.unit_price, ci.total_price, ci.businessid,
                       CASE 
                           WHEN ci.itemtype = 'chemical' THEN c.itemname
                           WHEN ci.itemtype = 'machinery' THEN m.itemname
                           WHEN ci.itemtype = 'service' THEN s.itemname
                       END as itemname,
                        CASE 
                           WHEN ci.itemtype = 'chemical' THEN c.image
                           WHEN ci.itemtype = 'machinery' THEN m.image
                           WHEN ci.itemtype = 'service' THEN s.image
                       END as image,
                       b.businessname
                FROM cart_items ci
                LEFT JOIN chemical c ON ci.itemid = c.itemid AND ci.itemtype = 'chemical' AND c.isdeleted = 0
                LEFT JOIN machinery m ON ci.itemid = m.itemid AND ci.itemtype = 'machinery' AND m.isdeleted = 0
                LEFT JOIN service s ON ci.itemid = s.itemid AND ci.itemtype = 'service' AND s.isdeleted = 0
                LEFT JOIN business b ON ci.businessid = b.userid
                WHERE ci.cartid = %s
                ORDER BY ci.added_at DESC
            """, (cart_id,))
            
            items = cursor.fetchall()
            
            # Calculate totals
            subtotal = sum(Decimal(str(item[5])) for item in items)
            commission = subtotal * self.commission_rate
            total = subtotal + commission
            
            cursor.close()
            conn.close()
            
           
            
            # Create a cart object with items as a list
            cart_data = {
                'cart_id': cart_id,
                'cart_items': [
                    {
                        'cart_item_id': item[0],
                        'itemid': item[1],
                        'itemtype': item[2],
                        'quantity': item[3],
                        'unit_price': float(item[4]),
                        'price': float(item[5]),
                        'businessid': item[6],
                        'itemname': item[7],
                        'businessname': item[9],
                        'itemimage':f"data:image/jpeg;base64,{base64.b64encode(item[8]).decode('utf-8') if item[8] else None}"
                       
                    } 
        
                    for item in items
                ],
                'total_amount': float(subtotal),
                'commission': float(commission),
                'final_total': float(total)
            }
            
            return cart_data
            
        except Exception as e:
            print(f"Error getting cart details: {e}")
            return {'cart_id': None, 'items': [], 'total_amount': 0, 'commission': 0, 'final_total': 0}
    
    def remove_from_cart(self, user_id: int, cart_item_id: int) -> bool:
        """Remove item from cart"""
        try:
            cart_id = self.get_or_create_cart(user_id)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM cart_items 
                WHERE cart_item_id = %s AND cartid = %s
            """, (cart_item_id, cart_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
            
        except Exception as e:
            print(f"Error removing from cart: {e}")
            return False
    
    def update_cart_quantity(self, user_id: int, cart_item_id: int, new_quantity: int) -> Dict:
        """Update quantity of item in cart"""
        try:
            if new_quantity <= 0:
                return {'success': False, 'message': 'Quantity must be greater than 0'}
            
            cart_id = self.get_or_create_cart(user_id)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get current item details
            cursor.execute("""
                SELECT itemid, itemtype, unit_price FROM cart_items 
                WHERE cart_item_id = %s AND cartid = %s
            """, (cart_item_id, cart_id))
            
            item = cursor.fetchone()
            if not item:
                cursor.close()
                conn.close()
                return {'success': False, 'message': 'Item not found in cart'}
            
            # Check stock availability (except for services)
            item_details = self._get_item_details(item[0], item[1])
            if item[1] != 'service' and new_quantity > item_details['quantityinstock']:
                cursor.close()
                conn.close()
                return {'success': False, 'message': f'Only {item_details["quantityinstock"]} units available'}
            
            # Update quantity and total price
            new_total_price = Decimal(str(item[2])) * new_quantity
            cursor.execute("""
                UPDATE cart_items 
                SET quantity = %s, total_price = %s 
                WHERE cart_item_id = %s
            """, (new_quantity, new_total_price, cart_item_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return {'success': True, 'message': 'Quantity updated successfully'}
            
        except Exception as e:
            print(f"Error updating cart quantity: {e}")
            return {'success': False, 'message': 'Error updating quantity'}

    def migrate_service_cart(self, user_id: int) -> bool:
        """Migrate existing service cart items to main cart"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get service cart items
            cursor.execute("""
                SELECT itemid, itemqty, price, businessid 
                FROM service_cart 
                WHERE userid = %s
            """, (user_id,))
            
            service_items = cursor.fetchall()
            
            if service_items:
                cart_id = self.get_or_create_cart(user_id)
                
                for item in service_items:
                    item_id, quantity, price, business_id = item
                    total_price = Decimal(str(price)) * quantity
                    
                    # Insert into main cart
                    cursor.execute("""
                        INSERT INTO cart_items (cartid, itemid, itemtype, quantity, unit_price, total_price, businessid)
                        VALUES (%s, %s, 'service', %s, %s, %s, %s)
                        ON CONFLICT (cartid, itemid, itemtype) DO UPDATE SET
                        quantity = cart_items.quantity + EXCLUDED.quantity,
                        total_price = cart_items.total_price + EXCLUDED.total_price
                    """, (cart_id, item_id, quantity, price, total_price, business_id))
                
                # Clear service cart
                cursor.execute("DELETE FROM service_cart WHERE userid = %s", (user_id,))
                
                conn.commit()
            
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error migrating service cart: {e}")
            return False

class OrderManager:
    """Manages order operations"""
    
    def __init__(self):
        self.commission_rate = Decimal('0.10')
    
    def create_order(self, user_id: int, shipping_address: str, cart_details: Dict) -> Optional[int]:
        """Create order from cart"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            order_cost = Decimal(str(cart_details['total_amount']))
            commission = Decimal(str(cart_details['commission']))
            total_cost = Decimal(str(cart_details['final_total']))
            
            cursor.execute("""
                INSERT INTO order_table (clientid, cartid, order_cost, honeybeehavencommision, 
                                       totalcost, shippingaddress, order_status, payment_status)
                VALUES (%s, %s, %s, %s, %s, %s, 'pending', 'pending')
                RETURNING orderid
            """, (user_id, cart_details['cart_id'], order_cost, commission, total_cost, shipping_address))
            
            order_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            conn.close()
            
            return order_id
            
        except Exception as e:
            print(f"Error creating order: {e}")
            return None
    
    def update_payment_status(self, order_id: int, payment_intent_id: str, status: str) -> bool:
        """Update order payment status"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE order_table 
                SET payment_status = %s, stripe_payment_intent_id = %s,
                    order_status = CASE WHEN %s = 'completed' THEN 'confirmed' ELSE order_status END
                WHERE orderid = %s
            """, (status, payment_intent_id, status, order_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
            
        except Exception as e:
            print(f"Error updating payment status: {e}")
            return False

class PaymentManager:
    """Manages Stripe payments"""
    
    @staticmethod
    def create_payment_intent(amount: float, currency: str = 'usd', order_id: int = None) -> Dict:
        """Create Stripe payment intent"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency,
                metadata={'order_id': order_id} if order_id else {}
            )
            
            return {
                'success': True,
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id
            }
            
        except Exception as e:
            print(f"Error creating payment intent: {e}")
            return {'success': False, 'error': str(e)}

class Product:
    """Base class for all products"""
    def __init__(self, name, price, description, image_data, business_id):
        self.name = name.strip()
        self.price = float(price)
        self.description = description.strip()
        self.image_data = image_data
        self.business_id = business_id
        self.date_created = datetime.now()
        self.isdeleted = 0
        self.issponsored = False
        self.itemrating = 0.0
    
    def validate_common_fields(self):
        """Validate common product fields"""
        errors = []
        
        if not self.name or len(self.name) < 2:
            errors.append("Product name must be at least 2 characters long")
        
        if self.price < 0:
            errors.append("Price cannot be negative")
        
        if not self.description or len(self.description) < 10:
            errors.append("Description must be at least 10 characters long")
        
        if not self.image_data:
            errors.append("Product image is required")
            
        return errors

class Machine(Product):
    """Machine product class"""
    def __init__(self, name, price, description, machine_type, dimensions, weight, 
                 power_source, warranty, quantity, image_data, business_id):
        super().__init__(name, price, description, image_data, business_id)
        self.machine_type = machine_type
        self.dimensions = f"{dimensions[0]}x{dimensions[1]}x{dimensions[2]}"
        self.weight = float(weight)
        self.power_source = power_source
        self.warranty = int(warranty)
        self.quantity = int(quantity)
    
    def validate_fields(self):
        """Validate machine-specific fields"""
        errors = self.validate_common_fields()
        
        if not self.machine_type:
            errors.append("Machine type is required")
        
        if self.weight <= 0:
            errors.append("Weight must be greater than 0")
        
        if not self.power_source:
            errors.append("Power source is required")
        
        if self.warranty < 0:
            errors.append("Warranty cannot be negative")
        
        if self.quantity < 0:
            errors.append("Quantity cannot be negative")
            
        return errors
    
    def save_to_database(self):
        """Save machine to database"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO machinery (itemname, item_price, itemdescription, machinetype,
                                     machinedimension, machineweight, powersource, warranty,
                                     quantityinstock, image, businessid, itemrating, 
                                     date_created, isdeleted, issponsored)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING itemid
            """, (
                self.name, self.price, self.description, self.machine_type,
                self.dimensions, self.weight, self.power_source, self.warranty,
                self.quantity, self.image_data, self.business_id, self.itemrating,
                self.date_created, self.isdeleted, self.issponsored
            ))
            
            item_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            conn.close()
            return item_id
        except Exception as e:
            print(f"Error saving machine: {e}")
            if conn:
                conn.rollback()
                conn.close()
            return None

class Chemical(Product):
    """Chemical product class"""
    def __init__(self, name, price, description, chemical_type, metric_system,
                 expiry_date, quantity, hazard_level, stock_quantity, image_data, business_id):
        super().__init__(name, price, description, image_data, business_id)
        self.chemical_type = chemical_type
        self.metric_system = metric_system
        self.expiry_date = expiry_date
        self.quantity = float(quantity)
        self.hazard_level = float(hazard_level)
        self.stock_quantity = int(stock_quantity)
    
    def validate_fields(self):
        """Validate chemical-specific fields"""
        errors = self.validate_common_fields()
        
        if not self.chemical_type:
            errors.append("Chemical type is required")
        
        if not self.metric_system:
            errors.append("Metric system is required")
        
        if not self.expiry_date:
            errors.append("Expiry date is required")
        else:
            try:
                expiry = datetime.strptime(self.expiry_date, '%Y-%m-%d').date()
                if expiry <= date.today():
                    errors.append("Expiry date must be in the future")
            except ValueError:
                errors.append("Invalid expiry date format")
        
        if self.quantity <= 0:
            errors.append("Quantity must be greater than 0")
        
        if self.hazard_level < 0 or self.hazard_level > 10:
            errors.append("Hazard level must be between 0 and 10")
        
        if self.stock_quantity < 0:
            errors.append("Stock quantity cannot be negative")
            
        return errors
    
    def save_to_database(self):
        """Save chemical to database"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO chemical (itemname, item_price, itemdescription, chemical_type,
                                    metricsystem, expirydate, quantity, hazardlevel,
                                    quantityinstock, image, businessid, itemrating,
                                    date_created, isdeleted, issponsored)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING itemid
            """, (
                self.name, self.price, self.description, self.chemical_type,
                self.metric_system, self.expiry_date, self.quantity, self.hazard_level,
                self.stock_quantity, self.image_data, self.business_id, self.itemrating,
                self.date_created, self.isdeleted, self.issponsored
            ))
            
            item_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            conn.close()
            return item_id
        except Exception as e:
            print(f"Error saving chemical: {e}")
            if conn:
                conn.rollback()
                conn.close()
            return None

class Service(Product):
    """Service product class"""
    def __init__(self, name, price, description, service_type, availability,
                 base_charges, image_data, business_id):
        super().__init__(name, price, description, image_data, business_id)
        self.service_type = service_type
        self.availability = availability.lower() == 'true'
        self.base_charges = float(base_charges)
    
    def validate_fields(self):
        """Validate service-specific fields"""
        errors = self.validate_common_fields()
        
        if not self.service_type:
            errors.append("Service type is required")
        
        if self.base_charges < 0:
            errors.append("Base charges cannot be negative")
            
        return errors
    
    def save_to_database(self):
        """Save service to database"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO service (itemname, item_price, itemdescription, servicetype,
                                   isavailable, basecharges, image, businessid, itemrating,
                                   date_created, isdeleted, issponsored)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING itemid
            """, (
                self.name, self.price, self.description, self.service_type,
                self.availability, self.base_charges, self.image_data, self.business_id,
                self.itemrating, self.date_created, self.isdeleted, self.issponsored
            ))
            
            item_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            conn.close()
            return item_id
        except Exception as e:
            print(f"Error saving service: {e}")
            if conn:
                conn.rollback()
                conn.close()
            return None

# Client Manager class (demonstrates encapsulation and polymorphism)
class ClientManager:
    """Manages client-related operations"""
    
    @staticmethod
    def get_client_data(client_id: int) -> Optional[Dict[str, Any]]:
        """Get client data with image handling"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("SELECT * FROM client WHERE userid = %s", (client_id,))
            client = cursor.fetchone()
            
            if client:
                client_dict = dict(client)
                # Handle image data
                if client_dict.get('image'):
                    client_dict['image_base64'] = base64.b64encode(client_dict['image']).decode('utf-8')
                    client_dict['image_url'] = f"data:image/jpeg;base64,{client_dict['image_base64']}"
                else:
                    client_dict['image_url'] = '../static/images/client-profile-placeholder.jpg'
                
                cursor.close()
                conn.close()
                return client_dict
            
            cursor.close()
            conn.close()
            return None
        except Exception as e:
            print(f"Error getting client data: {e}")
            return None
    
    @staticmethod
    def update_client(client_id: int, form_data: Dict[str, str], uploaded_file) -> Dict[str, Any]:
        """Update client information with validation"""
        errors = {}
        
        try:
            # Validate form data
            if form_data['name'] and len(form_data['name']) < 2:
                errors['name'] = 'Name must be at least 2 characters long'
            
            if form_data['age'] and not form_data['age'].isdigit():
                errors['age'] = 'Age must be a valid number'
            
            if form_data['address'] and len(form_data['address']) < 5:
                errors['address'] = 'Address must be at least 5 characters long'
            
            if form_data['gender'] and form_data['gender'] not in ['male', 'female', 'other']:
                errors['gender'] = 'Please select a valid gender'
            
            # Password validation if provided
            if form_data['current_password'] or form_data['new_password']:
                if not form_data['current_password']:
                    errors['current_password'] = 'Current password is required'
                elif not form_data['new_password']:
                    errors['new_password'] = 'New password is required'
                elif form_data['new_password'] != form_data['confirm_password']:
                    errors['confirm_password'] = 'Passwords do not match'
                else:
                    # Validate new password strength
                    password_errors = PasswordValidator.validate_password(
                        form_data['new_password'], form_data['confirm_password']
                    )
                    errors.update(password_errors)
                    
                    # Verify current password
                    if not errors:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT password FROM client WHERE userid = %s", (client_id,))
                        current_hash = cursor.fetchone()[0]
                        cursor.close()
                        conn.close()
                        
                        if not check_password_hash(current_hash, form_data['current_password']):
                            errors['current_password'] = 'Current password is incorrect'
            
            # Handle file upload
            image_data = None
            if uploaded_file and uploaded_file.filename:
                if not FileHandler.allowed_file(uploaded_file.filename):
                    errors['image'] = 'Invalid file type. Please upload PNG, JPG, or JPEG files.'
                else:
                    # Check file size (1MB limit)
                    uploaded_file.seek(0, 2)  # Seek to end
                    file_size = uploaded_file.tell()
                    uploaded_file.seek(0)  # Reset to beginning
                    
                    if file_size > app.config['MAX_CONTENT_LENGTH']:
                        errors['image'] = 'File size exceeds 1MB limit'
                    else:
                        image_data = FileHandler.get_file_binary_data(uploaded_file)
            
            if errors:
                return {'success': False, 'errors': errors}
            
            # Update database
            conn = get_db_connection()
            cursor = conn.cursor()
            
            update_fields = []
            update_values = []
            
            if form_data['name']:
                update_fields.append("name = %s")
                update_values.append(form_data['name'])
            
            if form_data['age']:
                update_fields.append("age = %s")
                update_values.append(form_data['age'])
            
            if form_data['address']:
                update_fields.append("address = %s")
                update_values.append(form_data['address'])
            
            if form_data['primary_location']:
                update_fields.append("primarylocation = %s")
                update_values.append(form_data['primary_location'])
            
            if form_data['gender']:
                update_fields.append("gender = %s")
                update_values.append(form_data['gender'])
            
            if form_data['new_password']:
                update_fields.append("password = %s")
                update_values.append(generate_password_hash(form_data['new_password']))
            
            if image_data:
                update_fields.append("image = %s")
                update_values.append(image_data)
            
            if update_fields:
                update_values.append(client_id)
                query = f"UPDATE client SET {', '.join(update_fields)} WHERE userid = %s"
                cursor.execute(query, update_values)
                conn.commit()
            
            cursor.close()
            conn.close()
            return {'success': True}
            
        except Exception as e:
            print(f"Error updating client: {e}")
            return {'success': False, 'errors': {'general': 'An error occurred while updating profile'}}

# Product Manager class for handling sponsored products
class ProductManager:
    """Manages product-related operations"""
    
    @staticmethod
    def get_sponsored_products(limit: int = 8) -> List[Dict[str, Any]]:
        """Get random sponsored products from all categories"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            products = []
            
            # Get sponsored chemicals
            cursor.execute("""
                SELECT itemid, itemname, item_price, itemdescription, image, 
                       itemrating, quantityinstock, 'Chemical' as category,
                       chemical_type as subcategory
                FROM chemical 
                WHERE issponsored = true AND isdeleted != 1 
                ORDER BY RANDOM() 
                LIMIT %s
            """, (limit // 3,))
            products.extend(cursor.fetchall())
            
            # Get sponsored machinery
            cursor.execute("""
                SELECT itemid, itemname, item_price, itemdescription, image,
                       itemrating, quantityinstock, 'Machinery' as category,
                       machinetype as subcategory
                FROM machinery 
                WHERE issponsored = true AND isdeleted != 1 
                ORDER BY RANDOM() 
                LIMIT %s
            """, (limit // 3,))
            products.extend(cursor.fetchall())
            
            # Get sponsored services
            cursor.execute("""
                SELECT itemid, itemname, item_price, itemdescription, image,
                       itemrating, 0 as quantityinstock, 'Service' as category,
                       servicetype as subcategory
                FROM service 
                WHERE issponsored = true AND isdeleted != 1 
                ORDER BY RANDOM() 
                LIMIT %s
            """, (limit // 3,))
            products.extend(cursor.fetchall())
            
            # Convert to list of dictionaries and handle images
            product_list = []
            for product in products:
                product_dict = dict(product)
                
                # Handle image data
                if product_dict.get('image'):
                    try:
                        image_data = product_dict['image']
                        
                        if isinstance(image_data, str):
                            product_dict['image_url'] = f"data:image/jpeg;base64,{image_data}"
                        elif isinstance(image_data, (bytes, memoryview)):
                            if isinstance(image_data, memoryview):
                                image_bytes = image_data.tobytes()
                            else:
                                image_bytes = image_data
                            
                            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                            product_dict['image_url'] = f"data:image/jpeg;base64,{image_base64}"
                        else:
                            product_dict['image_url'] = '../static/images/product-placeholder.jpg'
                            
                    except Exception as e:
                        print(f"Error processing image: {e}")
                        product_dict['image_url'] = '../static/images/product-placeholder.jpg'
                else:
                    product_dict['image_url'] = '../static/images/product-placeholder.jpg'
                
                
                # Format price
                if product_dict.get('item_price'):
                    product_dict['formatted_price'] = f"$ {product_dict['item_price']:.2f}"
                else:
                    product_dict['formatted_price'] = "Price on request"
                
                # Format rating
                if product_dict.get('itemrating'):
                    product_dict['formatted_rating'] = f"{product_dict['itemrating']:.1f}"
                else:
                    product_dict['formatted_rating'] = "No rating"
                
                product_list.append(product_dict)
            
            cursor.close()
            conn.close()
            
            # Shuffle and limit to requested number
            random.shuffle(product_list)
            return product_list[:limit]
            
        except Exception as e:
            print(f"Error getting sponsored products: {e}")
            return []
    
    @staticmethod
    def get_product_details(item_id: int, product_type: str) -> Optional[Dict[str, Any]]:
        """Get detailed product information by ID and type"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if product_type.lower() == 'chemical':
                cursor.execute("""
                    SELECT c.*, b.businessname, b.userid as business_userid,
                           AVG(r.rating) as avg_rating, COUNT(r.rating) as review_count
                    FROM chemical c
                    LEFT JOIN business b ON c.businessid = b.userid
                    LEFT JOIN review r ON c.itemid = r.itemid
                    WHERE c.itemid = %s AND c.isdeleted != 1
                    GROUP BY c.itemid, b.businessname, b.userid
                """, (item_id,))
            elif product_type.lower() == 'machinery':
                cursor.execute("""
                    SELECT m.*, b.businessname, b.userid as business_userid,
                           AVG(r.rating) as avg_rating, COUNT(r.rating) as review_count
                    FROM machinery m
                    LEFT JOIN business b ON m.businessid = b.userid
                    LEFT JOIN review r ON m.itemid = r.itemid
                    WHERE m.itemid = %s AND m.isdeleted != 1
                    GROUP BY m.itemid, b.businessname, b.userid
                """, (item_id,))
            elif product_type.lower() == 'service':
                cursor.execute("""
                    SELECT s.*, b.businessname, b.userid as business_userid,
                           AVG(r.rating) as avg_rating, COUNT(r.rating) as review_count
                    FROM service s
                    LEFT JOIN business b ON s.businessid = b.userid
                    LEFT JOIN review r ON s.itemid = r.itemid
                    WHERE s.itemid = %s AND s.isdeleted != 1
                    GROUP BY s.itemid, b.businessname, b.userid
                """, (item_id,))
            else:
                return None
            
            product = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if product:
                product_dict = dict(product)
                product_dict['product_type'] = product_type.lower()
                
                # Convert quantityinstock to integer for proper comparison
                try:
                    if product_dict.get('quantityinstock') is not None:
                        product_dict['quantityinstock'] = int(product_dict['quantityinstock'])
                    else:
                        product_dict['quantityinstock'] = 0
                except (ValueError, TypeError):
                    product_dict['quantityinstock'] = 0
                
                # Convert item_price to float for proper formatting
                try:
                    if product_dict.get('item_price') is not None:
                        product_dict['item_price'] = float(product_dict['item_price'])
                    else:
                        product_dict['item_price'] = 0.0
                except (ValueError, TypeError):
                    product_dict['item_price'] = 0.0
                
                # Handle image data
                if product_dict.get('image'):
                    try:
                        image_data = product_dict['image']
                        
                        if isinstance(image_data, str):
                            product_dict['image_url'] = f"data:image/jpeg;base64,{image_data}"
                        elif isinstance(image_data, (bytes, memoryview)):
                            if isinstance(image_data, memoryview):
                                image_bytes = image_data.tobytes()
                            else:
                                image_bytes = image_data
                            
                            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                            product_dict['image_url'] = f"data:image/jpeg;base64,{image_base64}"
                        else:
                            product_dict['image_url'] = '../static/images/product-placeholder.jpg'
                            
                    except Exception as e:
                        print(f"Error processing image: {e}")
                        product_dict['image_url'] = '../static/images/product-placeholder.jpg'
                else:
                    product_dict['image_url'] = '../static/images/product-placeholder.jpg'
                
                # Format rating
                if product_dict.get('avg_rating'):
                    try:
                        product_dict['formatted_rating'] = f"{float(product_dict['avg_rating']):.1f}"
                    except (ValueError, TypeError):
                        product_dict['formatted_rating'] = "No rating"
                else:
                    product_dict['formatted_rating'] = "No rating"
                
                return product_dict
            
            return None
            
        except Exception as e:
            print(f"Error getting product details: {e}")
            return None
    
    @staticmethod
    def get_product_reviews(item_id: int,producttype) -> List[Dict[str, Any]]:
        """Get all reviews for a product"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT r.*, c.name as client_name
                FROM review r
                LEFT JOIN client c ON r.clientid = c.userid
                WHERE r.itemid = %s AND r.producttype = %s
                ORDER BY r.date DESC
            """, (item_id,producttype))
            
            reviews = cursor.fetchall()
            cursor.close()
            conn.close()
            
            review_list = []
            for review in reviews:
                review_dict = dict(review)
                if not review_dict.get('client_name'):
                    review_dict['client_name'] = 'Anonymous'
                
                review_list.append(review_dict)
            
            return review_list
            
        except Exception as e:
            print(f"Error getting product reviews: {e}")
            return []
# Order Manager class for handling order operations

# Abstract base class for users (demonstrating inheritance and polymorphism)
class User(ABC):
    """Abstract base class for all users - demonstrates inheritance"""
    
    def __init__(self, name: str, email: str, password: str, address: str, primary_location: str):
        self._name = name  # Encapsulation - protected attribute
        self._email = email
        self._password_hash = generate_password_hash(password)
        self._address = address
        self._primary_location = primary_location
        self._date_joined = datetime.now().strftime("%Y-%m-%d")
        self._is_banned = False
        self._date_banned = None
        self._image_data = None  # Changed to store binary data
    
    # Getter methods (encapsulation)
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def email(self) -> str:
        return self._email
    
    @property
    def password_hash(self) -> str:
        return self._password_hash
    
    @property
    def address(self) -> str:
        return self._address
    
    @property
    def primary_location(self) -> str:
        return self._primary_location
    
    @property
    def date_joined(self) -> str:
        return self._date_joined
    
    @property
    def is_banned(self) -> bool:
        return self._is_banned
    
    @property
    def image_data(self) -> Optional[bytes]:
        return self._image_data
    
    # Setter methods (encapsulation)
    def set_image_data(self, image_data: bytes):
        """Store image as binary data"""
        self._image_data = image_data
    
    def ban_user(self):
        self._is_banned = True
        self._date_banned = datetime.now().strftime("%Y-%m-%d")
    
    def unban_user(self):
        self._is_banned = False
        self._date_banned = None
    
    def verify_password(self, password: str) -> bool:
        return check_password_hash(self._password_hash, password)
    
    @abstractmethod
    def save_to_database(self) -> bool:
        """Abstract method to be implemented by subclasses - demonstrates polymorphism"""
        pass
    
    @abstractmethod
    def get_user_type(self) -> str:
        """Abstract method to get user type"""
        pass
    
    def validate_common_fields(self) -> Dict[str, str]:
        """Common validation for all users"""
        errors = {}
        
        if not self._name or len(self._name.strip()) < 2:
            errors['name'] = 'Name must be at least 2 characters long'
        
        if not self._email or not self._is_valid_email(self._email):
            errors['email'] = 'Invalid email format'
        
        if not self._address or len(self._address.strip()) < 5:
            errors['address'] = 'Address must be at least 5 characters long'
        
        if not self._primary_location:
            errors['primary_location'] = 'Primary location is required'
        
        return errors
    
    def _is_valid_email(self, email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None


class Client(User):
    """Client class inheriting from User - demonstrates inheritance"""
    
    def __init__(self, name: str, email: str, password: str, address: str, 
                 primary_location: str, age: str, gender: str):
        super().__init__(name, email, password, address, primary_location)
        self._age = age
        self._gender = gender
    
    @property
    def age(self) -> str:
        return self._age
    
    @property
    def gender(self) -> str:
        return self._gender
    
    def get_user_type(self) -> str:
        return "client"
    
    def validate_fields(self) -> Dict[str, str]:
        """Client-specific validation"""
        errors = self.validate_common_fields()
        
        if not self._age:
            errors['age'] = 'Age is required'
        
        if not self._gender or self._gender not in ['male', 'female', 'other']:
            errors['gender'] = 'Valid gender selection is required'
        
        return errors
    
    def save_to_database(self) -> bool:
        """Polymorphic implementation for client"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO client (name, email, password, address, primarylocation, 
                                  age, gender, datejoined, is_banned, date_banned, image)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                self._name, self._email, self._password_hash, self._address,
                self._primary_location, self._age, self._gender, self._date_joined,
                self._is_banned, self._date_banned, self._image_data
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving client: {e}")
            if conn:
                conn.close()
            return False


class Business(User):
    """Business class inheriting from User - demonstrates inheritance"""
    
    def __init__(self, name: str, email: str, password: str, address: str,
                 primary_location: str, business_name: str, contact_info: str,
                 bank_account_number: str, business_description: str, target_keywords: str):
        super().__init__(name, email, password, address, primary_location)
        self._business_name = business_name
        self._contact_info = contact_info
        self._bank_account_number = bank_account_number
        self._business_description = business_description
        self._target_keywords = target_keywords
        self._business_rating = 0.0
    
    @property
    def business_name(self) -> str:
        return self._business_name
    
    @property
    def contact_info(self) -> str:
        return self._contact_info
    
    @property
    def bank_account_number(self) -> str:
        return self._bank_account_number
    
    @property
    def business_description(self) -> str:
        return self._business_description
    
    @property
    def target_keywords(self) -> str:
        return self._target_keywords
    
    @property
    def business_rating(self) -> float:
        return self._business_rating
    
    def get_user_type(self) -> str:
        return "business"
    
    def validate_fields(self) -> Dict[str, str]:
        """Business-specific validation"""
        errors = self.validate_common_fields()
        
        if not self._business_name or len(self._business_name.strip()) < 2:
            errors['business_name'] = 'Business name must be at least 2 characters long'
        
        if not self._contact_info or not self._is_valid_phone(self._contact_info):
            errors['contact_info'] = 'Invalid contact number format (must be  123-456-7890 or +1 (123) 456-7890)'
        
        if not self._bank_account_number or not self._is_valid_account_number(self._bank_account_number):
            errors['bank_account_number'] = 'Invalid account number format'
        
        if not self._business_description or len(self._business_description.strip()) < 10:
            errors['business_description'] = 'Business description must be at least 10 characters long'
        
        # Validate keywords count
        if self._target_keywords:
            keyword_count = len([k.strip() for k in self._target_keywords.split(',') if k.strip()])
            if keyword_count < 2 or keyword_count > 5:
                errors['target_keywords'] = 'Must select between 2 and 5 keywords'
        else:
            errors['target_keywords'] = 'At least 2 keywords must be selected'
        
        return errors
    
    def _is_valid_phone(self, phone: str) -> bool:
     pattern = r'^(?:\+1\s*|1\s*)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}$'
     return re.match(pattern, phone.strip()) is not None
    
    def _is_valid_account_number(self, account_number: str) -> bool:
        # Assuming account number should be digits and reasonable length
        return account_number.isdigit() and 10 <= len(account_number) <= 20
    
    def save_to_database(self) -> bool:
        """Polymorphic implementation for business"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO business (name, email, password, address, primarylocation,
                                    businessname, contactinfo, bankaccountnumber,
                                    businessdescription, targetkeywords, businessrating,
                                    datejoined, is_banned, date_banned, image)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                self._name, self._email, self._password_hash, self._address,
                self._primary_location, self._business_name, self._contact_info,
                self._bank_account_number, self._business_description, self._target_keywords,
                self._business_rating, self._date_joined, self._is_banned,
                self._date_banned, self._image_data
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving business: {e}")
            if conn:
                conn.close()
            return False


# Authentication Manager class (demonstrates encapsulation)
class AuthManager:
    """Handles authentication operations"""
    
    @staticmethod
    def login_user(email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user and return user data if successful"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Check client table
            cursor.execute("SELECT * FROM client WHERE email = %s", (email,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user['password'], password):
                user_dict = dict(user)
                # Convert image binary data to base64 for client-side storage
                if user_dict.get('image'):
                    user_dict['image_base64'] = base64.b64encode(user_dict['image']).decode('utf-8')
                    # Remove binary data before sending to client
                    del user_dict['image']
                user_dict['user_type'] = 'client'
                cursor.close()
                conn.close()
                return user_dict
            
            # Check business table
            cursor.execute("SELECT * FROM business WHERE email = %s", (email,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user['password'], password):
                user_dict = dict(user)
                # Convert image binary data to base64 for client-side storage
                if user_dict.get('image'):
                    user_dict['image_base64'] = base64.b64encode(user_dict['image']).decode('utf-8')
                    # Remove binary data before sending to client
                    del user_dict['image']
                user_dict['user_type'] = 'business'
                cursor.close()
                conn.close()
                return user_dict
            
            cursor.close()
            conn.close()
            return None
        except Exception as e:
            print(f"Login error: {e}")
            return None
    
    @staticmethod
    def email_exists(email: str) -> bool:
        """Check if email already exists in either table"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT email FROM client WHERE email = %s", (email,))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return True
            
            cursor.execute("SELECT email FROM business WHERE email = %s", (email,))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return True
            
            cursor.close()
            conn.close()
            return False
        except Exception as e:
            print(f"Email check error: {e}")
            return False


# File Handler class (demonstrates encapsulation)
class FileHandler:
    """Handles file upload operations"""
    
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    
    @staticmethod
    def allowed_file(filename: str) -> bool:
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in FileHandler.ALLOWED_EXTENSIONS
    
    @staticmethod
    def get_file_binary_data(file) -> Optional[bytes]:
        """Read file and return binary data"""
        if file and file.filename and FileHandler.allowed_file(file.filename):
            file.seek(0)  # Reset file pointer to beginning
            binary_data = file.read()
            return binary_data
        return None


# Password Validator class (demonstrates encapsulation)
class PasswordValidator:
    """Validates password strength"""
    
    @staticmethod
    def validate_password(password: str, confirm_password: str) -> Dict[str, str]:
        errors = {}
        
        if not password:
            errors['password'] = 'Password is required'
            return errors
        
        if len(password) < 8:
            errors['password'] = 'Password must be at least 8 characters long'
        
        if not re.search(r'[A-Z]', password):
            errors['password'] = 'Password must contain at least one uppercase letter'
        
        if not re.search(r'\d', password):
            errors['password'] = 'Password must contain at least one number'
        
        if password != confirm_password:
            errors['confirm_password'] = 'Passwords do not match'
        
        return errors

cart_manager = CartManager()

order_manager = OrderManager()
# Product creation classes

@app.route('/api/add-to-cart', methods=['POST'])
def add_to_cart():
    """Add item to cart API endpoint"""
    if 'user_id' not in session or session.get('user_type') != 'client':
        return jsonify({'success': False, 'message': 'Please login to add items to cart'}), 401
    
    try:
        data = request.get_json()
        user_id = session['user_id']
        item_id = data.get('item_id')
        item_type = data.get('item_type')
        quantity = data.get('quantity', 1)
        
        if not all([item_id, item_type]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        result = cart_manager.add_to_cart(user_id, item_id, item_type, quantity)
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in add_to_cart: {e}")
        return jsonify({'success': False, 'message': 'Error adding item to cart'}), 500

@app.route('/HoneyBeeHaven/cart')
def view_cart():
    """Display cart page"""
    if 'user_id' not in session or session.get('user_type') != 'client':
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Migrate any existing service cart items
    #cart_manager.migrate_service_cart(user_id)
    
    # Get cart details
    cart_details = cart_manager.get_cart_details(user_id)
    
    return render_template('honeybeehaven/client/cart.html', cart=cart_details)

@app.route('/api/remove-from-cart', methods=['POST'])
def remove_from_cart():
    """Remove item from cart"""
    if 'user_id' not in session or session.get('user_type') != 'client':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        cart_item_id = data.get('cart_item_id')
        
        if not cart_item_id:
            return jsonify({'success': False, 'message': 'Cart item ID required'}), 400
        
        success = cart_manager.remove_from_cart(session['user_id'], cart_item_id)
        
        if success:
            return jsonify({'success': True, 'message': 'Item removed from cart'})
        else:
            return jsonify({'success': False, 'message': 'Error removing item'}), 500
            
    except Exception as e:
        print(f"Error removing from cart: {e}")
        return jsonify({'success': False, 'message': 'Error removing item'}), 500

@app.route('/api/update-cart-quantity', methods=['POST'])
def update_cart_quantity():
    """Update item quantity in cart"""
    if 'user_id' not in session or session.get('user_type') != 'client':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        cart_item_id = data.get('cart_item_id')
        new_quantity = data.get('quantity')
        
        if not all([cart_item_id, new_quantity]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        result = cart_manager.update_cart_quantity(session['user_id'], cart_item_id, new_quantity)
        return jsonify(result)
        
    except Exception as e:
        print(f"Error updating cart quantity: {e}")
        return jsonify({'success': False, 'message': 'Error updating quantity'}), 500

@app.route('/HoneyBeeHaven/checkout')
def checkout():
    """Display checkout page"""
    if 'user_id' not in session or session.get('user_type') != 'client':
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    cart_details = cart_manager.get_cart_details(user_id)
    
    if not cart_details['cart_items']:
        flash('Your cart is empty', 'error')
        return redirect(url_for('view_cart'))
    
    return render_template('honeybeehaven/client/checkout.html', cart=cart_details)

@app.route('/api/create-payment-intent', methods=['POST'])
def create_payment_intent():
    """Create Stripe payment intent"""
    if 'user_id' not in session or session.get('user_type') != 'client':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        shipping_address = data.get('shipping_address')
        
        if not shipping_address:
            return jsonify({'success': False, 'message': 'Shipping address required'}), 400
        
        user_id = session['user_id']
        cart_details = cart_manager.get_cart_details(user_id)
        
        if not cart_details['cart_items']:
            return jsonify({'success': False, 'message': 'Cart is empty'}), 400
        
        # Create order
        order_id = order_manager.create_order(user_id, shipping_address, cart_details)
        if not order_id:
            return jsonify({'success': False, 'message': 'Error creating order'}), 500
        
        # Create payment intent
        payment_result = PaymentManager.create_payment_intent(
            amount=cart_details['final_total'],
            order_id=order_id
        )
        
        if payment_result['success']:
            return jsonify({
                'success': True,
                'client_secret': payment_result['client_secret'],
                'order_id': order_id
            })
        else:
            return jsonify({'success': False, 'message': payment_result['error']}), 500
            
    except Exception as e:
        print(f"Error creating payment intent: {e}")
        return jsonify({'success': False, 'message': 'Error processing payment'}), 500

@app.route('/api/confirm-payment', methods=['POST'])
def confirm_payment():
    """Confirm payment and complete order"""
    if 'user_id' not in session or session.get('user_type') != 'client':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        payment_intent_id = data.get('payment_intent_id')
        order_id = data.get('order_id')
        
        if not all([payment_intent_id, order_id]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        # Verify payment with Stripe
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            if intent.status == 'succeeded':
                # Update order status and create order details
                success = complete_order_with_details(order_id, payment_intent_id)
                
                if success:
                    # Create new cart for user
                    cart_manager.get_or_create_cart(session['user_id'])
                    insert_notification(session['user_id'],f'Your order {order_id} has been placed successfully')
                    
                    return jsonify({
                        'success': True,
                        'message': 'Payment successful! Order confirmed.',
                        'order_id': order_id
                    })
                else:
                    return jsonify({'success': False, 'message': 'Error processing order'}), 500
            else:
                order_manager.update_payment_status(order_id, payment_intent_id, 'failed')
                return jsonify({'success': False, 'message': 'Payment failed'}), 400
                
        except stripe.error.StripeError as e:
            print(f"Stripe error: {e}")
            return jsonify({'success': False, 'message': 'Payment verification failed'}), 500
            
    except Exception as e:
        print(f"Error confirming payment: {e}")
        return jsonify({'success': False, 'message': 'Error confirming payment'}), 500

def complete_order_with_details(order_id: int, payment_intent_id: str) -> bool:
    """Complete order by updating payment status and creating order details"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update payment status
        cursor.execute("""
            UPDATE order_table 
            SET payment_status = 'completed', 
                stripe_payment_intent_id = %s,
                order_status = 'confirmed'
            WHERE orderid = %s
        """, (payment_intent_id, order_id))
        
        # Get cart items for this order
        cursor.execute("""
            SELECT ci.itemid, ci.itemtype, ci.quantity, ci.businessid
            FROM order_table ot
            JOIN cart_items ci ON ot.cartid = ci.cartid
            WHERE ot.orderid = %s
        """, (order_id,))
        
        items = cursor.fetchall()
        
        # Insert order details for each item
        for item in items:
            item_id, item_type, quantity, business_id = item
            
            cursor.execute("""
                INSERT INTO order_details (orderid, itemid, itemtype, itemqty)
                VALUES (%s, %s, %s, %s)
            """, (order_id, item_id, item_type, quantity))
            
            # Update inventory (skip services)
            if item_type == 'chemical':
                cursor.execute("""
                    UPDATE chemical 
                    SET quantityinstock = quantityinstock - %s 
                    WHERE itemid = %s
                """, (quantity, item_id))
            elif item_type == 'machinery':
                cursor.execute("""
                    UPDATE machinery 
                    SET quantityinstock = quantityinstock - %s 
                    WHERE itemid = %s
                """, (quantity, item_id))
        
        # Deactivate the cart
        cursor.execute("""
            UPDATE cart 
            SET is_active = false 
            WHERE cartid = (SELECT cartid FROM order_table WHERE orderid = %s)
        """, (order_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"Error completing order: {e}")
        return False

def update_inventory_after_purchase(order_id: int):
    """Update inventory quantities after successful purchase"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get cart items for this order
        cursor.execute("""
            SELECT ci.itemid, ci.itemtype, ci.quantity
            FROM order_table ot
            JOIN cart_items ci ON ot.cartid = ci.cartid
            WHERE ot.orderid = %s
        """, (order_id,))
        
        items = cursor.fetchall()
        
        for item in items:
            item_id, item_type, quantity = item
            
            # Update inventory (skip services as they don't have physical stock)
            if item_type == 'chemical':
                cursor.execute("""
                    UPDATE chemical 
                    SET quantityinstock = quantityinstock - %s 
                    WHERE itemid = %s
                """, (quantity, item_id))
            elif item_type == 'machinery':
                cursor.execute("""
                    UPDATE machinery 
                    SET quantityinstock = quantityinstock - %s 
                    WHERE itemid = %s
                """, (quantity, item_id))
            # Services don't need inventory updates
        
        # Deactivate the cart
        cursor.execute("""
            UPDATE cart 
            SET is_active = false 
            WHERE cartid = (
                SELECT cartid FROM order_table WHERE orderid = %s
            )
        """, (order_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error updating inventory: {e}")


@app.route('/api/cart-count')
def cart_count():
    """Get cart item count for current user"""
    if 'user_id' not in session or session.get('user_type') != 'client':
        return jsonify({'count': 0})
    
    user_id = session['user_id']
    cart_details = cart_manager.get_cart_details(user_id)
    
    return jsonify({'count': len(cart_details['items'])})

@app.route('/HoneyBeeHaven/order-success/<int:order_id>')
def order_success(order_id):
    """Display order success page"""
    if 'user_id' not in session or session.get('user_type') != 'client':
        return redirect(url_for('login'))
    
    # Verify order belongs to current user
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT orderid, totalcost, orderdate 
            FROM order_table 
            WHERE orderid = %s AND clientid = %s
        """, (order_id, session['user_id']))
        
        order = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not order:
            flash('Order not found', 'error')
            return redirect(url_for('client_dashboard'))
        
        return render_template('honeybeehaven/client/order_success.html', order={
            'orderid': order[0],
            'totalcost': order[1],
            'orderdate': order[2]
        })
        
    except Exception as e:
        print(f"Error getting order: {e}")
        flash('Error retrieving order details', 'error')
        return redirect(url_for('client_dashboard'))


@app.route('/HoneyBeeHaven/client_order_history')
def client_order_history():
    """Display client order history"""
    if 'user_id' not in session or session.get('user_type') != 'client':
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all orders with items for the client
        cursor.execute("""
            SELECT 
                ot.orderid,
                ot.orderdate,
                ot.totalcost,
                ot.order_status,
                ot.shippingaddress,
                od.orderdetailkey,
                od.itemid,
                od.itemtype,
                od.itemqty,
                od.item_dispatch_date,
                od.item_delivery_date,
                od.delivery_status,
                CASE 
                    WHEN od.itemtype = 'chemical' THEN c.itemname
                    WHEN od.itemtype = 'machinery' THEN m.itemname
                    WHEN od.itemtype = 'service' THEN s.itemname
                END as item_name,
                CASE 
                    WHEN od.itemtype = 'chemical' THEN c.item_price
                    WHEN od.itemtype = 'machinery' THEN m.item_price
                    WHEN od.itemtype = 'service' THEN s.item_price
                END as item_price,
                CASE 
                    WHEN od.itemtype = 'chemical' THEN c.businessid
                    WHEN od.itemtype = 'machinery' THEN m.businessid
                    WHEN od.itemtype = 'service' THEN s.businessid
                END as businessid,
                COALESCE(r.rating, 0) as user_rating,
                CASE WHEN r.reviewid IS NOT NULL THEN true ELSE false END as has_reviewed
            FROM order_table ot
            JOIN order_details od ON ot.orderid = od.orderid
            LEFT JOIN chemical c ON od.itemid = c.itemid AND od.itemtype = 'chemical'
            LEFT JOIN machinery m ON od.itemid = m.itemid AND od.itemtype = 'machinery'
            LEFT JOIN service s ON od.itemid = s.itemid AND od.itemtype = 'service'
            LEFT JOIN review r ON od.itemid = r.itemid 
                AND r.clientid = %s 
                AND r.producttype = od.itemtype
                AND r.orderid = od.orderid
            WHERE ot.clientid = %s AND ot.payment_status = 'completed'
            ORDER BY ot.orderdate DESC, ot.orderid, od.orderdetailkey
        """, (session['user_id'], session['user_id']))
        
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Group orders by orderid
        orders_dict = {}  # Changed variable name to avoid confusion
        for row in results:
            order_id = row[0]
            if order_id not in orders_dict:
                orders_dict[order_id] = {
                    'orderid': row[0],
                    'orderdate': row[1].strftime('%Y-%m-%d') if row[1] else '',
                    'totalcost': float(row[2]) if row[2] else 0,
                    'order_status': row[3],
                    'shippingaddress': row[4],
                    'items': [],
                    'all_delivered': True
                }
            
            # Add item details
            item_total = float(row[13]) * row[8] if row[13] and row[8] else 0
            item = {
                'orderdetailkey': row[5],
                'itemid': row[6],
                'itemtype': row[7],
                'itemqty': row[8],
                'item_dispatch_date': row[9] if row[9] else 'Not dispatched',
                'item_delivery_date': row[10] if row[10] else 'Not delivered',
                'delivery_status': row[11] if row[11] else 'Processing',
                'item_name': row[12],
                'item_price': float(row[13]) if row[13] else 0,
                'item_total': item_total,
                'businessid': row[14],
                'user_rating': row[15],
                'has_reviewed': row[16]
            }
            
            orders_dict[order_id]['items'].append(item)
            
            # Check if all items are delivered
            if item['delivery_status'] != 'Delivered':
                orders_dict[order_id]['all_delivered'] = False
        
        # Update order status if all items are delivered
        for order in orders_dict.values():
            if order['all_delivered'] and order['order_status'] != 'Delivered':
                update_order_status_if_complete(order['orderid'])
                order['order_status'] = 'Delivered'
        
        # Convert to list for template
        orders_list = list(orders_dict.values())
        
        
        return render_template('honeybeehaven/client/clientOrderHistory.html', orders=orders_list)
        
    except Exception as e:
        print(f"Error getting order history: {e}")
        import traceback
        traceback.print_exc()  # This will give you the full error traceback
        flash('Error loading order history', 'error')
        return redirect(url_for('client_dashboard'))
    
def update_order_status_if_complete(order_id: int):
    """Update order status to delivered if all items are delivered"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE order_table 
            SET order_status = 'Delivered' 
            WHERE orderid = %s
        """, (order_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error updating order status: {e}")


@app.route('/api/submit-review', methods=['POST'])
def submit_review_delivered():
    """Submit a review for an item in a specific order"""
    if 'user_id' not in session or session.get('user_type') != 'client':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        orderdetailkey = data.get('orderdetailkey')
        rating = data.get('rating')
        review_text = data.get('review_text')
        review_title = data.get('review_title')
        
        if not all([orderdetailkey, rating]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        # Validate rating
        try:
            rating = int(rating)
            if not (1 <= rating <= 5):
                return jsonify({'success': False, 'message': 'Rating must be between 1 and 5'}), 400
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid rating format'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get item details and order ID from order_details
        cursor.execute("""
            SELECT od.itemid, od.itemtype, od.orderid
            FROM order_details od
            JOIN order_table ot ON od.orderid = ot.orderid
            WHERE od.orderdetailkey = %s 
            AND ot.clientid = %s
            AND od.delivery_status = 'Delivered'
        """, (orderdetailkey, session['user_id']))
        
        result = cursor.fetchone()
        if not result:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Item not found or not delivered'}), 404
        
        itemid, itemtype, orderid = result
        
        # Check if review already exists for this specific order and item
        cursor.execute("""
            SELECT reviewid FROM review 
            WHERE clientid = %s AND orderid = %s AND itemid = %s AND producttype = %s
        """, (session['user_id'], orderid, itemid, itemtype))
        
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Review already submitted for this item in this order'}), 400
        
        # Insert the review with order ID
        current_date = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            INSERT INTO review (clientid, orderid, date, itemid, rating, text, title, producttype)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (session['user_id'], orderid, current_date, itemid, rating, review_text or '', review_title or '', itemtype))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Review submitted successfully'})
        
    except Exception as e:
        print(f"Error submitting review: {e}")
        return jsonify({'success': False, 'message': 'Database error'}), 500

@app.route('/api/update-delivery-status', methods=['POST'])
def update_delivery_status():
    """Update delivery status to delivered"""
    if 'user_id' not in session or session.get('user_type') != 'client':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        orderdetailkey = data.get('orderdetailkey')
        
        if not orderdetailkey:
            return jsonify({'success': False, 'message': 'Missing orderdetailkey'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update delivery status and delivery date
        current_date = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            UPDATE order_details 
            SET delivery_status = 'Delivered',
                item_delivery_date = %s
            WHERE orderdetailkey = %s 
            AND orderid IN (
                SELECT orderid FROM order_table WHERE clientid = %s
            )
        """, (current_date, orderdetailkey, session['user_id']))
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Order detail not found or unauthorized'}), 404
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Delivery status updated successfully'})
        
    except Exception as e:
        print(f"Error updating delivery status: {e}")
        return jsonify({'success': False, 'message': 'Database error'}), 500
    
@app.route('/HoneyBeeHaven/business_orders')
def business_orders():
    """Display orders for business"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get orders that contain items from this business
        cursor.execute("""
            SELECT DISTINCT
                ot.orderid,
                ot.orderdate,
                ot.shippingaddress,
                ot.order_status,
                c.name as client_name,
                c.userid as client_id,
                c.email as client_email,
                COUNT(od.orderdetailkey) as total_items,
                SUM(CASE 
                    WHEN od.itemtype = 'chemical' THEN ch.item_price * od.itemqty
                    WHEN od.itemtype = 'machinery' THEN m.item_price * od.itemqty
                    WHEN od.itemtype = 'service' THEN s.item_price * od.itemqty
                END) as business_total
            FROM order_table ot
            JOIN client c ON ot.clientid = c.userid
            JOIN order_details od ON ot.orderid = od.orderid
            LEFT JOIN chemical ch ON od.itemid = ch.itemid AND od.itemtype = 'chemical' AND ch.businessid = %s
            LEFT JOIN machinery m ON od.itemid = m.itemid AND od.itemtype = 'machinery' AND m.businessid = %s
            LEFT JOIN service s ON od.itemid = s.itemid AND od.itemtype = 'service' AND s.businessid = %s
            WHERE ot.payment_status = 'completed'
            AND (ch.businessid = %s OR m.businessid = %s OR s.businessid = %s)
            GROUP BY ot.orderid, ot.orderdate, ot.shippingaddress, ot.order_status, c.name, c.userid, c.email
            ORDER BY ot.orderdate DESC
        """, (session['user_id'], session['user_id'], session['user_id'], 
              session['user_id'], session['user_id'], session['user_id']))
        
        orders = cursor.fetchall()
        cursor.close()
        conn.close()
        
        order_list = []
        for order in orders:
            order_dict = {
                'orderid': order[0],
                'orderdate': order[1].strftime('%Y-%m-%d') if order[1] else '',
                'shippingaddress': order[2],
                'order_status': order[3],
                'client_name': order[4],
                'client_id': order[5],
                'client_email': order[6],
                'total_items': order[7],
                'business_total': float(order[8]) if order[8] else 0
            }
            order_list.append(order_dict)
        
        return render_template('honeybeehaven/business/orderPage.html', orders=order_list)
        
    except Exception as e:
        print(f"Error getting business orders: {e}")
        flash('Error loading orders', 'error')
        return redirect(url_for('business_dashboard'))

@app.route('/api/get-order-items/<int:order_id>')
def get_order_items(order_id):
    """Get items in a specific order for the logged-in business"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                od.orderdetailkey,
                od.itemid,
                od.itemtype,
                od.itemqty,
                od.item_dispatch_date,
                od.item_delivery_date,
                od.delivery_status,
                CASE 
                    WHEN od.itemtype = 'chemical' THEN c.itemname
                    WHEN od.itemtype = 'machinery' THEN m.itemname
                    WHEN od.itemtype = 'service' THEN s.itemname
                END as item_name,
                CASE 
                    WHEN od.itemtype = 'chemical' THEN c.item_price
                    WHEN od.itemtype = 'machinery' THEN m.item_price
                    WHEN od.itemtype = 'service' THEN s.item_price
                END as item_price
            FROM order_details od
            LEFT JOIN chemical c ON od.itemid = c.itemid AND od.itemtype = 'chemical' AND c.businessid = %s
            LEFT JOIN machinery m ON od.itemid = m.itemid AND od.itemtype = 'machinery' AND m.businessid = %s
            LEFT JOIN service s ON od.itemid = s.itemid AND od.itemtype = 'service' AND s.businessid = %s
            WHERE od.orderid = %s
            AND (c.businessid = %s OR m.businessid = %s OR s.businessid = %s)
        """, (session['user_id'], session['user_id'], session['user_id'], 
              order_id, session['user_id'], session['user_id'], session['user_id']))
        
        items = cursor.fetchall()
        cursor.close()
        conn.close()
        
        item_list = []
        for item in items:
            item_dict = {
                'orderdetailkey': item[0],
                'itemid': item[1],
                'itemtype': item[2],
                'itemqty': item[3],
                'item_dispatch_date': item[4],
                'item_delivery_date': item[5],
                'delivery_status': item[6] or 'Processing',
                'item_name': item[7],
                'item_price': float(item[8]) if item[8] else 0,
                'item_total': float(item[8]) * item[3] if item[8] and item[3] else 0
            }
            item_list.append(item_dict)
        
        return jsonify({'success': True, 'items': item_list})
        
    except Exception as e:
        print(f"Error getting order items: {e}")
        return jsonify({'success': False, 'message': 'Error loading items'}), 500

@app.route('/api/update-item-status', methods=['POST'])
def update_item_status():
    """Update item dispatch/delivery status by business"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        orderdetailkey = data.get('orderdetailkey')
        action = data.get('action')  # 'dispatch' or 'deliver'
        
        if not all([orderdetailkey, action]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if action == 'dispatch':
            cursor.execute("""
                UPDATE order_details 
                SET item_dispatch_date = CURRENT_DATE,
                    delivery_status = 'Dispatched'
                WHERE orderdetailkey = %s
                AND orderid IN (
                    SELECT DISTINCT od.orderid 
                    FROM order_details od
                    LEFT JOIN chemical c ON od.itemid = c.itemid AND od.itemtype = 'chemical'
                    LEFT JOIN machinery m ON od.itemid = m.itemid AND od.itemtype = 'machinery'
                    LEFT JOIN service s ON od.itemid = s.itemid AND od.itemtype = 'service'
                    WHERE (c.businessid = %s OR m.businessid = %s OR s.businessid = %s)
                )
            """, (orderdetailkey, session['user_id'], session['user_id'], session['user_id']))
        elif action == 'deliver':
            cursor.execute("""
                UPDATE order_details 
                SET item_delivery_date = CURRENT_DATE,
                    delivery_status = 'Delivered'
                WHERE orderdetailkey = %s
                AND orderid IN (
                    SELECT DISTINCT od.orderid 
                    FROM order_details od
                    LEFT JOIN chemical c ON od.itemid = c.itemid AND od.itemtype = 'chemical'
                    LEFT JOIN machinery m ON od.itemid = m.itemid AND od.itemtype = 'machinery'
                    LEFT JOIN service s ON od.itemid = s.itemid AND od.itemtype = 'service'
                    WHERE (c.businessid = %s OR m.businessid = %s OR s.businessid = %s)
                )
            """, (orderdetailkey, session['user_id'], session['user_id'], session['user_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Item {action}ed successfully'})
        
    except Exception as e:
        print(f"Error updating item status: {e}")
        return jsonify({'success': False, 'message': 'Error updating status'}), 500


@app.route('/HoneyBeeHaven/view_client_profile/<int:client_id>')
def view_client_profile(client_id):
    """View client profile with enhanced information"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get client information
        cursor.execute("""
            SELECT userid, name, email, address, primarylocation,
                   age, gender, datejoined, image, is_banned, date_banned
            FROM client 
            WHERE userid = %s
        """, (client_id,))
        
        client = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not client:
            flash('Client not found', 'error')
            return redirect(url_for('login'))
        
        # Check if client is banned
        if client[9]:  # is_banned
            flash('This client account has been banned', 'warning')
        
        # Format the date if available
        date_joined = client[7]
        if date_joined:
            try:
                # If date is stored as string, parse it
                if isinstance(date_joined, str):
                    date_obj = datetime.strptime(date_joined, '%Y-%m-%d')
                    formatted_date = date_obj.strftime('%B %d, %Y')
                else:
                    formatted_date = date_joined.strftime('%B %d, %Y')
            except:
                formatted_date = str(date_joined)
        else:
            formatted_date = 'Not available'
        
        client_data = {
            'userid': client[0],
            'name': client[1],
            'email': client[2],
            'address': client[3],
            'primarylocation': client[4],
            'age': client[5],
            'gender': client[6],
            'datejoined': formatted_date,
            'has_image': client[8] is not None,  # image
            'is_banned': client[9],
            'date_banned': client[10]
        }
        
        return render_template('honeybeehaven/shared/ViewClientProfile.html', client=client_data)
        
    except Exception as e:
        print(f"Error viewing client profile: {e}")
        flash('Error loading profile', 'error')
        return redirect(url_for('index'))


@app.route('/HoneyBeeHaven/client_image/<int:client_id>')
def get_client_image(client_id):
    """Serve client profile image from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT image FROM client WHERE userid = %s", (client_id,))
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result and result[0]:
            # Convert bytea to bytes and serve as image
            image_data = bytes(result[0])
            return Response(image_data, mimetype='image/jpeg')
        else:
            # Return default image or 404
            return redirect(url_for('static', filename='images/default-user.jpg'))
            
    except Exception as e:
        print(f"Error serving client image: {e}")
        return redirect(url_for('static', filename='images/default-user.jpg'))



# Route for create item page
@app.route('/HoneyBeeHaven/createitem')
def create_item():
    """Show create item page for business users"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        flash('Access denied. Business login required.', 'error')
        return redirect(url_for('login'))
    
    return render_template('honeybeehaven/business/createItem.html')

# Route for machine submission
@app.route('/HoneyBeeHaven/submitmachine', methods=['POST'])
def submit_machine():
    """Handle machine creation"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return jsonify({'success': False, 'message': 'Access denied. Business login required.'}), 403
    
    try:
        # Get form data
        name = request.form.get('mname', '').strip()
        price = request.form.get('mprice', '0')
        description = request.form.get('mdesc', '').strip()
        machine_type = request.form.get('mtype', '')
        dim1 = request.form.get('mdimensions1', '0')
        dim2 = request.form.get('mdimensions2', '0')
        dim3 = request.form.get('mdimensions3', '0')
        weight = request.form.get('mweight', '0')
        power_source = request.form.get('mfuel', '')
        warranty = request.form.get('mwarr', '0')
        quantity = request.form.get('mquantity', '0')
        
        # Handle file upload
        file = request.files.get('file1')
        if not file or not file.filename:
            return jsonify({'success': False, 'message': 'Machine image is required'}), 400
        
        image_data = FileHandler.get_file_binary_data(file)
        if not image_data:
            return jsonify({'success': False, 'message': 'Invalid image file. Please upload JPG, JPEG, or PNG'}), 400
        
        # Create machine object
        machine = Machine(
            name, price, description, machine_type,
            [dim1, dim2, dim3], weight, power_source,
            warranty, quantity, image_data, session['user_id']
        )
        
        # Validate fields
        validation_errors = machine.validate_fields()
        if validation_errors:
            return jsonify({'success': False, 'message': '; '.join(validation_errors)}), 400
        
        # Save to database
        item_id = machine.save_to_database()
        if item_id:
            insert_notification( session['user_id'],f'Your Product {name} is live now!')
            return jsonify({'success': True, 'message': 'Machine created successfully!', 'item_id': item_id})
        else:
            return jsonify({'success': False, 'message': 'Failed to create machine. Please try again.'}), 500
    
    except Exception as e:
        print(f"Machine creation error: {e}")
        return jsonify({'success': False, 'message': 'An error occurred. Please try again.'}), 500

# Route for chemical submission
@app.route('/HoneyBeeHaven/submitchemical', methods=['POST'])
def submit_chemical():
    """Handle chemical creation"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return jsonify({'success': False, 'message': 'Access denied. Business login required.'}), 403
    
    try:
        # Get form data
        name = request.form.get('cname', '').strip()
        price = request.form.get('cprice', '0')
        description = request.form.get('cdesc', '').strip()
        chemical_type = request.form.get('ctype', '')
        metric_system = request.form.get('metricsystem', '')
        expiry_date = request.form.get('cedate', '')
        quantity = request.form.get('cquan', '0')
        hazard_level = request.form.get('hazard', '0')
        stock_quantity = request.form.get('cquantity', '0')
        
        # Handle file upload
        file = request.files.get('file2')
        if not file or not file.filename:
            return jsonify({'success': False, 'message': 'Chemical image is required'}), 400
        
        image_data = FileHandler.get_file_binary_data(file)
        if not image_data:
            return jsonify({'success': False, 'message': 'Invalid image file. Please upload JPG, JPEG, or PNG'}), 400
        
        # Create chemical object
        chemical = Chemical(
            name, price, description, chemical_type, metric_system,
            expiry_date, quantity, hazard_level, stock_quantity,
            image_data, session['user_id']
        )
        
        # Validate fields
        validation_errors = chemical.validate_fields()
        if validation_errors:
            return jsonify({'success': False, 'message': '; '.join(validation_errors)}), 400
        
        # Save to database
        item_id = chemical.save_to_database()
        if item_id:
            insert_notification( session['user_id'],f'Your Product {name} is live now!')
            return jsonify({'success': True, 'message': 'Chemical created successfully!', 'item_id': item_id})
        else:
            return jsonify({'success': False, 'message': 'Failed to create chemical. Please try again.'}), 500
    
    except Exception as e:
        print(f"Chemical creation error: {e}")
        return jsonify({'success': False, 'message': 'An error occurred. Please try again.'}), 500

# Route for service submission
@app.route('/HoneyBeeHaven/submitservice', methods=['POST'])
def submit_service():
    """Handle service creation"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return jsonify({'success': False, 'message': 'Access denied. Business login required.'}), 403
    
    try:
        # Get form data
        name = request.form.get('sname', '').strip()
        price = request.form.get('sprice', '0')
        description = request.form.get('sdesc', '').strip()
        service_type = request.form.get('stype', '')
        availability = request.form.get('availability', '')
        base_charges = request.form.get('sbase', '0')
        
        # Handle file upload
        file = request.files.get('file3')
        if not file or not file.filename:
            return jsonify({'success': False, 'message': 'Service image is required'}), 400
        
        image_data = FileHandler.get_file_binary_data(file)
        if not image_data:
            return jsonify({'success': False, 'message': 'Invalid image file. Please upload JPG, JPEG, or PNG'}), 400
        
        # Create service object
        service = Service(
            name, price, description, service_type,
            availability, base_charges, image_data, session['user_id']
        )
        
        # Validate fields
        validation_errors = service.validate_fields()
        if validation_errors:
            return jsonify({'success': False, 'message': '; '.join(validation_errors)}), 400
        
        # Save to database
        item_id = service.save_to_database()
        if item_id:
            insert_notification( session['user_id'],f'Your Service {name} is live now!')
            return jsonify({'success': True, 'message': 'Service created successfully!', 'item_id': item_id})
        else:
            return jsonify({'success': False, 'message': 'Failed to create service. Please try again.'}), 500
    
    except Exception as e:
        print(f"Service creation error: {e}")
        return jsonify({'success': False, 'message': 'An error occurred. Please try again.'}), 500


def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG)

@app.route('/HoneyBeeHaven/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            subject = request.form.get('subject', '').strip()
            message = request.form.get('message', '').strip()
            
            # Validate required fields
            if not all([name, email, subject, message]):
                flash('All fields are required!', 'error')
                return render_template('contact.html')
            
            # Connect to database and insert data
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Insert or update contact information
            insert_query = """
                INSERT INTO public.contact (email, name, subject, message) 
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (email) 
                DO UPDATE SET 
                    name = EXCLUDED.name,
                    subject = EXCLUDED.subject,
                    message = EXCLUDED.message
            """
            
            cursor.execute(insert_query, (email, name, subject, message))
            conn.commit()
            
            cursor.close()
            conn.close()
            
            flash('Thank you for your message! We will get back to you soon.', 'success')
            return redirect(url_for('contact'))
            
        except psycopg2.Error as e:
            flash(f'Database error: {str(e)}', 'error')
            return render_template('contact.html')
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
            return render_template('contact.html')
    
    # GET request - display the contact form
    return render_template('honeybeehaven/home/contact.html')
# Routes

@app.route('/')
def index():
    return render_template('honeybeehaven/index.html')


@app.route('/HoneyBeeHaven/client_signup')
def client_signup():
    return render_template('honeybeehaven/client/customer_signup.html')


@app.route('/HoneyBeeHaven/business_signup')
def business_signup():
    return render_template('honeybeehaven/business/business_signup.html')


@app.route('/HoneyBeeHaven/login')
def login():
    # Check if user is already logged in
    if 'user_id' in session:
        if session.get('user_type') == 'client':
            return redirect(url_for('client_dashboard'))
        elif session.get('user_type') == 'business':
            return redirect(url_for('business_dashboard'))
    
    return render_template('honeybeehaven/home/login.html')


@app.route('/HoneyBeeHaven/submitClientSignup', methods=['POST'])
def submit_client_signup():
    try:
        # Get form data
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirmpassword', '')
        age = request.form.get('age', '')
        gender = request.form.get('gender', '')
        primary_location = request.form.get('primary', '')
        address = request.form.get('address', '').strip()
        
        # Validate password
        password_errors = PasswordValidator.validate_password(password, confirm_password)
        if password_errors:
            return render_template('honeybeehaven/client/customer_signup.html', 
                                 error=1, error_message='Invalid password requirements')
        
        # Check if email exists
        if AuthManager.email_exists(email):
            return render_template('honeybeehaven/client/customer_signup.html', 
                                 error=2, error_message='Email already exists')
        
        # Create client object
        client = Client(name, email, password, address, primary_location, age, gender)
        
        # Validate fields
        validation_errors = client.validate_fields()
        if validation_errors:
            return render_template('honeybeehaven/client/customer_signup.html', 
                                 error=1, error_message='Invalid field data')
        
        # Handle file upload
        file = request.files.get('file')
        if file and file.filename:
            if file.content_length and file.content_length > app.config['MAX_CONTENT_LENGTH']:
                return render_template('honeybeehaven/client/customer_signup.html', 
                                     error=3, error_message='File size exceeds 1MB limit')
            
            binary_data = FileHandler.get_file_binary_data(file)
            if binary_data:
                client.set_image_data(binary_data)
        
        # Save to database
        if client.save_to_database():
            flash('Client registration successful!', 'success')
            return redirect(url_for('login'))
        else:
            return render_template('honeybeehaven/client/customer_signup.html', 
                                 error=1, error_message='Registration failed')
    
    except Exception as e:
        print(f"Client signup error: {e}")
        return render_template('honeybeehaven/client/customer_signup.html', 
                             error=1, error_message='An error occurred during registration')


@app.route('/HoneyBeeHaven/submitBusinessSignup', methods=['POST'])
def submit_business_signup():
    try:
        # Get form data
        name = request.form.get('name', '').strip()
        business_name = request.form.get('businessName', '').strip()
        contact_info = request.form.get('contactInfo', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirmpassword', '')
        primary_location = request.form.get('primary', '')
        bank_account_number = request.form.get('bankaccountnumber', '').strip()
        address = request.form.get('address', '').strip()
        business_description = request.form.get('businessDescription', '').strip()
        
        # Get selected keywords
        selected_keywords = request.form.getlist('selectedKeywords')
        target_keywords = ','.join(selected_keywords) if selected_keywords else ''
        
        # Validate password
        password_errors = PasswordValidator.validate_password(password, confirm_password)
        if password_errors:
            return render_template('honeybeehaven/business/business_signup.html', 
                                 error=1, error_message='Invalid password requirements')
        
        # Check if email exists
        if AuthManager.email_exists(email):
            return render_template('honeybeehaven/business/business_signup.html', 
                                 error=2, error_message='Email already exists')
        
        # Create business object
        business = Business(name, email, password, address, primary_location,
                          business_name, contact_info, bank_account_number,
                          business_description, target_keywords)
        
        # Validate fields
        validation_errors = business.validate_fields()
        if validation_errors:
            return render_template('honeybeehaven/business/business_signup.html', 
                                 error=1, error_message='Invalid field data')
        
        # Handle file upload
        file = request.files.get('file')
        if file and file.filename:
            if file.content_length and file.content_length > app.config['MAX_CONTENT_LENGTH']:
                return render_template('honeybeehaven/business/business_signup.html', 
                                     error=3, error_message='File size exceeds 1MB limit')
            
            binary_data = FileHandler.get_file_binary_data(file)
            if binary_data:
                business.set_image_data(binary_data)
        
        # Save to database
        if business.save_to_database():
            flash('Business registration successful!', 'success')
            return redirect(url_for('login'))
        else:
            return render_template('honeybeehaven/business/business_signup.html', 
                                 error=1, error_message='Registration failed')
    
    except Exception as e:
        print(f"Business signup error: {e}")
        return render_template('honeybeehaven/business/business_signup.html', 
                             error=1, error_message='An error occurred during registration')


@app.route('/HoneyBeeHaven/submitLogin', methods=['POST'])
def submit_login():
    try:
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if not email or not password:
            return render_template('honeybeehaven/home/login.html', 
                                 error=1, error_message='Email and password are required')
        
        user_data = AuthManager.login_user(email, password)
        
        if user_data:
            if user_data.get('is_banned'):
                return render_template('honeybeehaven/home/login.html', 
                                     error=1, error_message='Your account has been banned')
            
            # Store user data in session
            session['user_id'] = user_data['userid']
            session['user_type'] = user_data['user_type']
            session['user_name'] = user_data['name']
            session['user_email'] = user_data['email']
            
            flash(f'Welcome back, {user_data["name"]}!', 'success')
            
            # Render login success page with user data for client-side storage
            if user_data['user_type'] == 'client':
                return render_template('honeybeehaven/home/login_success.html', 
                                     user_data=user_data, redirect_url=url_for('client_dashboard'))
            else:
                return render_template('honeybeehaven/home/login_success.html', 
                                     user_data=user_data, redirect_url=url_for('business_dashboard'))
        else:
            return render_template('honeybeehaven/home/login.html', 
                                 error=1, error_message='Invalid email or password')
    
    except Exception as e:
        print(f"Login error: {e}")
        return render_template('honeybeehaven/home/login.html', 
                             error=1, error_message='An error occurred during login')


@app.route('/HoneyBeeHaven/client_dashboard')
def client_dashboard():
    if 'user_id' not in session or session.get('user_type') != 'client':
        flash('Please log in to access the dashboard', 'error')
        return redirect(url_for('login'))
    
    try:
        # Get client data
        print('before client')
        client_data = ClientManager.get_client_data(session['user_id'])
        print('after client')
        if not client_data:
            print('if condition')
            flash('Client data not found', 'error')
            return redirect(url_for('login'))
        print('before sponsor')
        # Get sponsored products (randomly selecting from all product types)
        sponsored_products = ProductManager.get_sponsored_products()
        print('after sponsor')
        return render_template(
            'honeybeehaven/client/clientdashboard.html',
            client_data=client_data,
            sponsored_products=sponsored_products
        )
    except Exception as e:
        print(e)
        print(f"Dashboard error: {e}")
        flash('Error loading dashboard', 'error')
        return redirect(url_for('login'))

@app.route('/HoneyBeeHaven/edit_client')
def edit_client():
    if 'user_id' not in session or session.get('user_type') != 'client':
        flash('Please log in to access this page', 'error')
        return redirect(url_for('login'))
    
    try:
        client_data = ClientManager.get_client_data(session['user_id'])
        if not client_data:
            flash('Client data not found', 'error')
            return redirect(url_for('login'))
        
        return render_template(
            'honeybeehaven/client/edit_client.html',
            client_data=client_data,
            errors={},  # Add this line - initialize empty errors dict
            form_data={}  # Add this line - initialize empty form_data dict
        )
    except Exception as e:
        print(f"Edit client error: {e}")
        flash('Error loading profile data', 'error')
        return redirect(url_for('client_dashboard'))
    
@app.route('/HoneyBeeHaven/submit_edit_client', methods=['POST'])
def submit_edit_client():
    if 'user_id' not in session or session.get('user_type') != 'client':
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        client_id = session['user_id']
        
        # Get form data
        form_data = {
            'name': request.form.get('name', '').strip(),
            'age': request.form.get('age', '').strip(),
            'address': request.form.get('address', '').strip(),
            'primary_location': request.form.get('primary_location', '').strip(),
            'gender': request.form.get('gender', '').strip(),
            'current_password': request.form.get('current_password', ''),
            'new_password': request.form.get('new_password', ''),
            'confirm_password': request.form.get('confirm_password', '')
        }
        
        # Handle file upload
        uploaded_file = request.files.get('profile_image')
        
        # Validate and update client data
        result = ClientManager.update_client(client_id, form_data, uploaded_file)
        
        if result['success']:
            # Update session if name changed
            if form_data['name']:
                session['user_name'] = form_data['name']
            
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('client_dashboard'))
        else:
            # Return to edit page with errors
            client_data = ClientManager.get_client_data(client_id)
            return render_template(
                'honeybeehaven/client/edit_client.html',
                client_data=client_data,
                errors=result.get('errors', {}),
                form_data=form_data
            )
            
    except Exception as e:
        print(f"Update client error: {e}")
        flash('An error occurred while updating profile', 'error')
        return redirect(url_for('edit_client'))


def get_business_products(business_id):
    """Get all products for a business"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        products = []
        
        # Get machinery
        cursor.execute("""
            SELECT itemid, itemname, item_price, itemdescription, quantityinstock,
                   itemrating, date_created, 'machinery' as product_type
            FROM machinery 
            WHERE businessid = %s AND isdeleted != 1
            ORDER BY date_created DESC
        """, (business_id,))
        products.extend(cursor.fetchall())
        
        # Get chemicals
        cursor.execute("""
            SELECT itemid, itemname, item_price, itemdescription, quantityinstock,
                   itemrating, date_created, 'chemical' as product_type
            FROM chemical 
            WHERE businessid = %s AND isdeleted != 1
            ORDER BY date_created DESC
        """, (business_id,))
        products.extend(cursor.fetchall())
        
        # Get services
        cursor.execute("""
            SELECT itemid, itemname, item_price, itemdescription, 0 as quantityinstock,
                   itemrating, date_created, 'service' as product_type
            FROM service 
            WHERE businessid = %s AND isdeleted != 1
            ORDER BY date_created DESC
        """, (business_id,))
        products.extend(cursor.fetchall())
        
        cursor.close()
        conn.close()
        
        # Sort by date created (most recent first)
        products.sort(key=lambda x: x['date_created'], reverse=True)
        
        return products
        
    except Exception as e:
        print(f"Error getting business products: {e}")
        return []

@app.route('/HoneyBeeHaven/business_dashboard')
def business_dashboard():
    """Business dashboard page"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        flash('Please log in as a business user to access this page', 'error')
        return redirect(url_for('login'))
    
    try:
        # Get business products
        business_products = get_business_products(session['user_id'])
        return render_template('honeybeehaven/business/businessDashboard.html', 
                             products=business_products)
    except Exception as e:
        print(f"Dashboard error: {e}")
        flash('Error loading dashboard', 'error')
        return redirect(url_for('login'))

@app.route('/HoneyBeeHaven/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('login'))

@app.route('/HoneyBeeHaven/about')
def about():
    return render_template('honeybeehaven/home/about.html')



@app.route('/HoneyBeeHaven/privacyPolicy')
def privacy_policy():
    return render_template('honeybeehaven/home/privacyPolicy.html')

@app.route('/HoneyBeeHaven/termsAndConditions')
def terms_and_conditions():
    return render_template('honeybeehaven/home/termsAndConditions.html')

# API endpoint to get user data from client-side storage
@app.route('/api/user-data')
def get_user_data_api():
    """API endpoint to verify and return user data"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    return jsonify({
        'user_id': session['user_id'],
        'user_type': session['user_type'],
        'user_name': session['user_name'],
        'user_email': session['user_email']
    })

@app.route('/HoneyBeeHaven/view_product')
def view_product():
    """View individual product details"""
    if 'user_id' not in session:
        flash('Please log in to view products', 'error')
        return redirect(url_for('login'))
    
    item_id = request.args.get('id')
    product_type = request.args.get('type', '').lower()
    
    if not item_id or not product_type:
        flash('Invalid product link', 'error')
        return redirect(url_for('client_dashboard'))
    
    try:
        # Get product details
        product = ProductManager.get_product_details(int(item_id), product_type)
        if not product:
            flash('Product not found', 'error')
            return redirect(url_for('client_dashboard'))
        
        
        reviews = ProductManager.get_product_reviews(int(item_id), product_type)
        
        # Determine template based on product type
        if product_type == 'chemical':
            template = 'honeybeehaven/client/chemicalDesignPage.html'
        elif product_type == 'machinery':
            template = 'honeybeehaven/client/machineDesignPage.html'
        elif product_type == 'service':
            template = 'honeybeehaven/client/serviceDesignPage.html'
        else:
            flash('Invalid product type', 'error')
            return redirect(url_for('client_dashboard'))
        print("Product Types Debug:")
       
        return render_template(template, product=product, reviews=reviews)
        
    except Exception as e:
        print(f"Error viewing product: {e}")
        flash('Error loading product details', 'error')
        return redirect(url_for('client_dashboard'))


@app.route('/api/business-profile/<int:user_id>')
def get_business_profile(user_id):
    """API endpoint to get business profile data"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Ensure user can only access their own profile
    if session['user_id'] != user_id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT userid, name, email, address, primarylocation, businessname, 
                   contactinfo, bankaccountnumber, businessdescription, 
                   targetkeywords, businessrating, datejoined, image
            FROM business 
            WHERE userid = %s AND is_banned = FALSE
        """, (user_id,))
        
        business = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not business:
            return jsonify({'error': 'Business profile not found'}), 404
        
        # Convert to dict and handle image
        business_dict = dict(business)
        if business_dict.get('image'):
            business_dict['image_base64'] = base64.b64encode(business_dict['image']).decode('utf-8')
            del business_dict['image']  # Remove binary data
        
        return jsonify(business_dict)
        
    except Exception as e:
        print(f"Error fetching business profile: {e}")
        return jsonify({'error': 'Database error'}), 500
    
@app.route('/HoneyBeeHaven/edit_business')
def edit_business():
    """Route to edit business profile"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        flash('Please log in to access this page', 'error')
        return redirect(url_for('login'))
    
    # You'll need to create this template
    return render_template('honeybeehaven/business/edit_business.html')

@app.route('/HoneyBeeHaven/editbusiness', methods=['POST'])
def edit_business_update():
    """Handle business profile update with comprehensive validation"""
    
    # Check authentication
    if 'user_id' not in session or session.get('user_type') != 'business':
        return jsonify({'success': False, 'message': 'Authentication required'}), 401
    
    user_id = session['user_id']
    
    try:
        # Get form data
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        business_name = request.form.get('businessName', '').strip()
        username = request.form.get('name', '').strip()
        contact_info = request.form.get('contactInfo', '').strip()
        bank_account = request.form.get('bankaccountnumber', '').strip()
        address = request.form.get('address', '').strip()
        primary_location = request.form.get('primary', '').strip()
        business_description = request.form.get('businessDescription', '').strip()
        current_password = request.form.get('checkpassword', '').strip()
        new_password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirmpassword', '').strip()
        selected_keywords = request.form.getlist('selectedKeywords')
        
        # Validation dictionary for errors
        errors = {}
        
        # Validate required fields
        if not business_name:
            errors['businessName'] = 'Business name is required'
        elif len(business_name) > 100:
            errors['businessName'] = 'Business name must be less than 100 characters'
            
        if not username:
            errors['username'] = 'Username is required'
        elif len(username) > 50:
            errors['username'] = 'Username must be less than 50 characters'
        
            
        if not contact_info:
            errors['contactInfo'] = 'Contact number is required'
        elif not validate_canadian_phone(contact_info):
            errors['contactInfo'] = 'Please enter a valid Canadian phone number'
            
        if not bank_account:
            errors['bankAccountNumber'] = 'Bank account number is required'
        elif not re.match(r'^\d{7,20}$', bank_account):
            errors['bankAccountNumber'] = 'Bank account number must be 7-20 digits'
            
        if not address:
            errors['address'] = 'Business address is required'
        elif len(address) > 200:
            errors['address'] = 'Address must be less than 200 characters'
            
        if not primary_location:
            errors['primaryLocation'] = 'Primary location is required'
        elif primary_location not in ['Ontario', 'Quebec', 'Alberta', 'Saskatchewan', 'Manitoba', 
                                    'British Columbia', 'Nova Scotia', 'New Brunswick', 
                                    'Prince Edward Island', 'Newfoundland and Labrador', 
                                    'Northwest Territories', 'Yukon', 'Nunavut']:
            errors['primaryLocation'] = 'Please select a valid Canadian province/territory'
            
        if not business_description:
            errors['businessDescription'] = 'Business description is required'
        elif len(business_description) > 500:
            errors['businessDescription'] = 'Description must be less than 500 characters'
            
        if new_password or confirm_password:
    
         if not new_password:
             errors['newPassword'] = 'New password is required when changing password'
         elif not confirm_password:
             errors['confirmPassword'] = 'Please confirm your new password'
         else:
            # Validate new password strength
             if len(new_password) < 8:
                 errors['newPassword'] = 'Password must be at least 8 characters'
             elif not re.search(r'[A-Z]', new_password):
                 errors['newPassword'] = 'Password must contain at least one uppercase letter'
             elif not re.search(r'\d', new_password):
                 errors['newPassword'] = 'Password must contain at least one number'
             elif new_password != confirm_password:
                 errors['confirmPassword'] = 'Passwords do not match'
    
    # If user wants to change password, current password is required
         if (new_password or confirm_password) and not current_password:
             errors['currentPassword'] = 'Current password is required to change password'
            
        # Validate keywords
        if len(selected_keywords) < 2:
            errors['keywords'] = 'Please select at least 2 keywords'
        elif len(selected_keywords) > 5:
            errors['keywords'] = 'Please select maximum 5 keywords'
            
        # Validate new password if provided
        if new_password:
            if len(new_password) < 8:
                errors['newPassword'] = 'Password must be at least 8 characters'
            elif not re.search(r'[A-Z]', new_password):
                errors['newPassword'] = 'Password must contain at least one uppercase letter'
            elif not re.search(r'\d', new_password):
                errors['newPassword'] = 'Password must contain at least one number'
            elif new_password != confirm_password:
                errors['confirmPassword'] = 'Passwords do not match'
        elif confirm_password:
            errors['newPassword'] = 'Please enter a new password'
            
        password_change_requested = bool(new_password or confirm_password)
        if password_change_requested:
    # Verify current password
            cursor.execute("SELECT password FROM business WHERE userid = %s", (user_id,))
            result = cursor.fetchone()
    
            if not result:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'message': 'Business profile not found'}), 404
       
            stored_password = result[0]
            if not check_password_hash(stored_password,current_password):
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'errors': {'currentPassword': 'Current password is incorrect'}}), 400
        else:
    # No password change requested, just verify the business exists
            cursor.execute("SELECT userid FROM business WHERE userid = %s", (user_id,))
            result = cursor.fetchone()
    
            if not result:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'message': 'Business profile not found'}), 404
        image_data = None
        uploaded_file = request.files.get('file')
        if uploaded_file and uploaded_file.filename:
            # Validate file
            if not allowed_file(uploaded_file.filename):
                errors['file'] = 'Only JPG, JPEG, and PNG files are allowed'
            elif uploaded_file.content_length and uploaded_file.content_length > 1048576:  # 1MB
                errors['file'] = 'File size must be less than 1MB'
            else:
                try:
                    image_data = uploaded_file.read()
                    if len(image_data) > 1048576:  # Double-check file size
                        errors['file'] = 'File size must be less than 1MB'
                        image_data = None
                except Exception as e:
                    errors['file'] = 'Error processing image file'
                    image_data = None
                    
        # If there are validation errors, return them
        if errors:
            return jsonify({'success': False, 'errors': errors}), 400
            
        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        
            
        
        
            
        # Prepare update query
        update_fields = []
        update_values = []
        
        # Basic fields
        fields_map = {
            'businessname': business_name,
            'name': username,
            'contactinfo': contact_info,
            'bankaccountnumber': bank_account,
            'address': address,
            'primarylocation': primary_location,
            'businessdescription': business_description,
            'targetkeywords': ','.join(selected_keywords)
        }
        
        for field, value in fields_map.items():
            update_fields.append(f"{field} = %s")
            update_values.append(value)
            
        # Handle password update
        if new_password:
            hashed_password = generate_password_hash(new_password)
            update_fields.append("password = %s")
            update_values.append(hashed_password)
            
        # Handle image update
        if image_data:
            update_fields.append("image = %s")
            update_values.append(image_data)
            
        # Add user ID for WHERE clause
        update_values.append(user_id)
        
        # Execute update
        update_query = f"""
            UPDATE business 
            SET {', '.join(update_fields)}
            WHERE userid = %s AND is_banned = FALSE
        """
        
        cursor.execute(update_query, update_values)
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Failed to update profile or account is banned'}), 400
            
        conn.commit()
        cursor.close()
        conn.close()
        
        # Update session if username changed
        if username != session.get('username'):
            session['username'] = username
            
        return jsonify({
            'success': True, 
            'message': 'Profile updated successfully!',
            'data': {
                'businessname': business_name,
                'username': username
            }
        })
        
    except psycopg2.Error as e:
        print(f"Database error in edit_business: {e}")
        return jsonify({'success': False, 'message': 'Database error occurred'}), 500
        
    except Exception as e:
        print(f"Unexpected error in edit_business: {e}")
        return jsonify({'success': False, 'message': 'An unexpected error occurred'}), 500
    
def validate_canadian_phone(phone):
    pattern = r'^(?:\+1\s*|1\s*)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}$'
    return re.match(pattern, phone.strip()) is not None


def allowed_file(filename):
    """Check if uploaded file has allowed extension"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/HoneyBeeHaven/myProducts')
def my_products():
    """Display all products for logged in business user"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        flash('Please login as a business user to access this page', 'error')
        return redirect(url_for('login'))
    
    business_id = session['user_id']
    category = request.args.get('category', 'all')
    search = request.args.get('search', '')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        products = []
        
        # Base query conditions
        base_conditions = "businessid = %s AND isdeleted != 1"
        search_condition = ""
        params = [business_id]
        
        if search:
            search_condition = " AND LOWER(itemname) LIKE %s"
            search_param = f"%{search.lower()}%"
        
        # Get products based on category
        if category == 'all' or category == 'machinery':
            query = f"""
                SELECT itemid, itemname, item_price, itemdescription, quantityinstock,
                       itemrating, date_created, image, 'machinery' as product_type, machinetype as subtype
                FROM machinery 
                WHERE {base_conditions}{search_condition}
                ORDER BY date_created DESC
            """
            query_params = params + ([search_param] if search else [])
            cursor.execute(query, query_params)
            products.extend(cursor.fetchall())
        
        if category == 'all' or category == 'chemical':
            query = f"""
                SELECT itemid, itemname, item_price, itemdescription, quantityinstock,
                       itemrating, date_created, image, 'chemical' as product_type, chemical_type as subtype
                FROM chemical 
                WHERE {base_conditions}{search_condition}
                ORDER BY date_created DESC
            """
            query_params = params + ([search_param] if search else [])
            cursor.execute(query, query_params)
            products.extend(cursor.fetchall())
        
        if category == 'all' or category == 'service':
            query = f"""
                SELECT itemid, itemname, item_price, itemdescription, 0 as quantityinstock,
                       itemrating, date_created, image, 'service' as product_type, servicetype as subtype
                FROM service 
                WHERE {base_conditions}{search_condition}
                ORDER BY date_created DESC
            """
            query_params = params + ([search_param] if search else [])
            cursor.execute(query, query_params)
            products.extend(cursor.fetchall())
        
        cursor.close()
        conn.close()
        
        # Process products for display
        processed_products = []
        for product in products:
            product_dict = dict(product)
            
            # Handle image data
            if product_dict.get('image'):
                try:
                    image_data = product_dict['image']
                    
                    # Handle different data types from PostgreSQL bytea
                    if isinstance(image_data, str):
                        # Already base64 encoded string
                        product_dict['image_url'] = f"data:image/jpeg;base64,{image_data}"
                    elif isinstance(image_data, (bytes, memoryview)):
                        # Convert memoryview or bytes to base64
                        if isinstance(image_data, memoryview):
                            image_bytes = image_data.tobytes()
                        else:
                            image_bytes = image_data
                        
                        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                        product_dict['image_url'] = f"data:image/jpeg;base64,{image_base64}"
                    else:
                        print(f"Unexpected image data type: {type(image_data)}")
                        product_dict['image_url'] = '../static/images/product-placeholder.jpg'
                        
                except Exception as e:
                    print(f"Error processing image: {e}")
                    product_dict['image_url'] = '../static/images/product-placeholder.jpg'
            else:
                product_dict['image_url'] = '../static/images/product-placeholder.jpg'
            
            # Format price and rating
            product_dict['formatted_price'] = f"$ {product_dict['item_price']:.2f}" if product_dict['item_price'] else "Price on request"
            product_dict['formatted_rating'] = f"{product_dict['itemrating']:.1f}" if product_dict['itemrating'] else "No rating"
            
            processed_products.append(product_dict)
        
        # Sort by date if all categories
        if category == 'all':
            processed_products.sort(key=lambda x: x['date_created'] or '', reverse=True)
        
        return render_template('honeybeehaven/business/myProducts.html', 
                             products=processed_products, 
                             current_category=category,
                             search_query=search,
                             business_name=session.get('user_name', ''))
        
    except Exception as e:
        print(f"Error getting business products: {e}")
        flash('Error loading products', 'error')
        return render_template('honeybeehaven/business/myProducts.html', 
                             products=[], 
                             current_category=category,
                             search_query=search,
                             business_name=session.get('user_name', ''))

@app.route('/HoneyBeeHaven/deleteProduct/<product_type>/<int:item_id>')
def delete_product(product_type, item_id):
    """Delete a product (soft delete)"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        flash('Unauthorized access', 'error')
        return redirect(url_for('login'))
    
    business_id = session['user_id']
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify ownership and soft delete
        if product_type == 'machinery':
            cursor.execute("UPDATE machinery SET isdeleted = 1 WHERE itemid = %s AND businessid = %s", 
                         (item_id, business_id))
        elif product_type == 'chemical':
            cursor.execute("UPDATE chemical SET isdeleted = 1 WHERE itemid = %s AND businessid = %s", 
                         (item_id, business_id))
        elif product_type == 'service':
            cursor.execute("UPDATE service SET isdeleted = 1 WHERE itemid = %s AND businessid = %s", 
                         (item_id, business_id))
        
        if cursor.rowcount > 0:
            conn.commit()
            flash('Product deleted successfully', 'success')
        else:
            flash('Product not found or unauthorized', 'error')
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error deleting product: {e}")
        flash('Error deleting product', 'error')
    
    return redirect(url_for('my_products'))

@app.route('/HoneyBeeHaven/getProductData/<product_type>/<int:item_id>')
def get_product_data(product_type, item_id):
    """Get product data for editing"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return jsonify({'error': 'Unauthorized'}), 401
    
    business_id = session['user_id']
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        if product_type == 'machinery':
            cursor.execute("""
                SELECT * FROM machinery 
                WHERE itemid = %s AND businessid = %s AND isdeleted != 1
            """, (item_id, business_id))
        elif product_type == 'chemical':
            cursor.execute("""
                SELECT * FROM chemical 
                WHERE itemid = %s AND businessid = %s AND isdeleted != 1
            """, (item_id, business_id))
        elif product_type == 'service':
            cursor.execute("""
                SELECT * FROM service 
                WHERE itemid = %s AND businessid = %s AND isdeleted != 1
            """, (item_id, business_id))
        else:
            return jsonify({'error': 'Invalid product type'}), 400
        
        product = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if product:
            return jsonify(dict(product))
        else:
            return jsonify({'error': 'Product not found'}), 404
            
    except Exception as e:
        print(f"Error getting product data: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/HoneyBeeHaven/editMachine/<int:item_id>')
def edit_machine_page(item_id):
    """Display edit machine page"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        flash('Please login as a business user', 'error')
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT * FROM machinery 
            WHERE itemid = %s AND businessid = %s AND isdeleted != 1
        """, (item_id, session['user_id']))
        
        machine = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not machine:
            flash('Machine not found', 'error')
            return redirect(url_for('my_products'))
        
        return render_template('honeybeehaven/business/editMachine.html', machine=dict(machine))
        
    except Exception as e:
        print(f"Error loading machine: {e}")
        flash('Error loading machine data', 'error')
        return redirect(url_for('my_products'))

@app.route('/HoneyBeeHaven/editChemical/<int:item_id>')
def edit_chemical_page(item_id):
    """Display edit chemical page"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        flash('Please login as a business user', 'error')
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT * FROM chemical 
            WHERE itemid = %s AND businessid = %s AND isdeleted != 1
        """, (item_id, session['user_id']))
        
        chemical = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not chemical:
            flash('Chemical not found', 'error')
            return redirect(url_for('my_products'))
        
        return render_template('honeybeehaven/business/editChemical.html', chemical=dict(chemical))
        
    except Exception as e:
        print(f"Error loading chemical: {e}")
        flash('Error loading chemical data', 'error')
        return redirect(url_for('my_products'))

@app.route('/HoneyBeeHaven/editService/<int:item_id>')
def edit_service_page(item_id):
    """Display edit service page"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        flash('Please login as a business user', 'error')
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT * FROM service 
            WHERE itemid = %s AND businessid = %s AND isdeleted != 1
        """, (item_id, session['user_id']))
        
        service = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not service:
            flash('Service not found', 'error')
            return redirect(url_for('my_products'))
        
        return render_template('honeybeehaven/business/editService.html', service=dict(service))
        
    except Exception as e:
        print(f"Error loading service: {e}")
        flash('Error loading service data', 'error')
        return redirect(url_for('my_products'))

@app.route('/HoneyBeeHaven/editMachine', methods=['POST'])
def edit_machine():
    """Handle machine update"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get form data
        item_id = request.form.get('itemId')
        machine_name = request.form.get('mname', '').strip()
        machine_price = float(request.form.get('mprice', 0))
        description = request.form.get('mdesc', '').strip()
        weight = float(request.form.get('mweight', 0))
        warranty = int(request.form.get('mwarr', 0))
        quantity = int(request.form.get('mquantity', 0))
        
        # Validation
        errors = []
        if not machine_name:
            errors.append("Machine name is required")
        if machine_price < 0:
            errors.append("Price must be positive")
        if weight < 0:
            errors.append("Weight must be positive")
        if warranty < 0:
            errors.append("Warranty must be positive")
        if quantity < 0:
            errors.append("Quantity must be positive")
        
        if errors:
            flash('; '.join(errors), 'error')
            return redirect(url_for('edit_machine_page', item_id=item_id))
        
        # Handle file upload
        image_data = None
        uploaded_file = request.files.get('file')
        if uploaded_file and uploaded_file.filename:
            if allowed_file(uploaded_file.filename):
                image_data = uploaded_file.read()
                if len(image_data) > 1048576:  # 1MB
                    flash('File size must be less than 1MB', 'error')
                    return redirect(url_for('edit_machine_page', item_id=item_id))
        
        # Update query
        if image_data:
            cursor.execute("""
                UPDATE machinery 
                SET itemname = %s, item_price = %s, itemdescription = %s, 
                    machineweight = %s, warranty = %s, quantityinstock = %s, image = %s
                WHERE itemid = %s AND businessid = %s
            """, (machine_name, machine_price, description, weight, warranty, quantity, image_data, item_id, session['user_id']))
        else:
            cursor.execute("""
                UPDATE machinery 
                SET itemname = %s, item_price = %s, itemdescription = %s, 
                    machineweight = %s, warranty = %s, quantityinstock = %s
                WHERE itemid = %s AND businessid = %s
            """, (machine_name, machine_price, description, weight, warranty, quantity, item_id, session['user_id']))
        
        if cursor.rowcount > 0:
            conn.commit()
            flash('Machine updated successfully!', 'success')
        else:
            flash('Machine not found or unauthorized', 'error')
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error updating machine: {e}")
        flash('Error updating machine', 'error')
    
    return redirect(url_for('my_products'))

@app.route('/HoneyBeeHaven/editChemical', methods=['POST'])
def edit_chemical():
    """Handle chemical update"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get form data
        item_id = request.form.get('itemId')
        product_heading = request.form.get('productHeading', '').strip()
        product_price = float(request.form.get('productPrice', 0))
        description = request.form.get('productDescription', '').strip()
        expiry_date = request.form.get('expiryDate', '')
        quantity = float(request.form.get('quantity', 0))
        quantity_in_stock = int(request.form.get('quantityInStock', 0))
        
        # Validation
        errors = []
        if not product_heading:
            errors.append("Chemical name is required")
        if product_price < 0:
            errors.append("Price must be positive")
        if quantity < 0:
            errors.append("Quantity must be positive")
        if quantity_in_stock < 0:
            errors.append("Stock quantity must be positive")
        
        if errors:
            flash('; '.join(errors), 'error')
            return redirect(url_for('edit_chemical_page', item_id=item_id))
        
        # Handle file upload
        image_data = None
        uploaded_file = request.files.get('file')
        if uploaded_file and uploaded_file.filename:
            if allowed_file(uploaded_file.filename):
                image_data = uploaded_file.read()
                if len(image_data) > 1048576:  # 1MB
                    flash('File size must be less than 1MB', 'error')
                    return redirect(url_for('edit_chemical_page', item_id=item_id))
        
        # Update query
        if image_data:
            cursor.execute("""
                UPDATE chemical 
                SET itemname = %s, item_price = %s, itemdescription = %s, 
                    expirydate = %s, quantity = %s, quantityinstock = %s, image = %s
                WHERE itemid = %s AND businessid = %s
            """, (product_heading, product_price, description, expiry_date, quantity, quantity_in_stock, image_data, item_id, session['user_id']))
        else:
            cursor.execute("""
                UPDATE chemical 
                SET itemname = %s, item_price = %s, itemdescription = %s, 
                    expirydate = %s, quantity = %s, quantityinstock = %s
                WHERE itemid = %s AND businessid = %s
            """, (product_heading, product_price, description, expiry_date, quantity, quantity_in_stock, item_id, session['user_id']))
        
        if cursor.rowcount > 0:
            conn.commit()
            flash('Chemical updated successfully!', 'success')
        else:
            flash('Chemical not found or unauthorized', 'error')
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error updating chemical: {e}")
        flash('Error updating chemical', 'error')
    
    return redirect(url_for('my_products'))

@app.route('/HoneyBeeHaven/editService', methods=['POST'])
def edit_service():
    """Handle service update"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get form data
        item_id = request.form.get('itemId')
        service_name = request.form.get('sname', '').strip()
        service_price = float(request.form.get('sprice', 0))
        description = request.form.get('sdesc', '').strip()
        availability = request.form.get('availability') == 'true'
        base_charges = float(request.form.get('sbase', 0))
        
        # Validation
        errors = []
        if not service_name:
            errors.append("Service name is required")
        if service_price < 0:
            errors.append("Price must be positive")
        if base_charges < 0:
            errors.append("Base charges must be positive")
        
        if errors:
            flash('; '.join(errors), 'error')
            return redirect(url_for('edit_service_page', item_id=item_id))
        
        # Handle file upload
        image_data = None
        uploaded_file = request.files.get('file')
        if uploaded_file and uploaded_file.filename:
            if allowed_file(uploaded_file.filename):
                image_data = uploaded_file.read()
                if len(image_data) > 1048576:  # 1MB
                    flash('File size must be less than 1MB', 'error')
                    return redirect(url_for('edit_service_page', item_id=item_id))
        
        # Update query
        if image_data:
            cursor.execute("""
                UPDATE service 
                SET itemname = %s, item_price = %s, itemdescription = %s, 
                    isavailable = %s, basecharges = %s, image = %s
                WHERE itemid = %s AND businessid = %s
            """, (service_name, service_price, description, availability, str(base_charges), image_data, item_id, session['user_id']))
        else:
            cursor.execute("""
                UPDATE service 
                SET itemname = %s, item_price = %s, itemdescription = %s, 
                    isavailable = %s, basecharges = %s
                WHERE itemid = %s AND businessid = %s
            """, (service_name, service_price, description, availability, str(base_charges), item_id, session['user_id']))
        
        if cursor.rowcount > 0:
            conn.commit()
            flash('Service updated successfully!', 'success')
        else:
            flash('Service not found or unauthorized', 'error')
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error updating service: {e}")
        flash('Error updating service', 'error')
    
    return redirect(url_for('my_products'))



@app.route('/HoneyBeeHaven/marketplace')
def marketplace():
    """Display the marketplace page"""
    # Get filter parameters from URL
    search_query = request.args.get('search', '')
    rating = request.args.get('rating', '')
    location = request.args.get('location', '')
    mtype = request.args.get('mtype', '')
    ctype = request.args.get('ctype', '')
    stype = request.args.get('stype', '')
    
    return render_template('honeybeehaven/shared/marketplace.html',
                         search_query=search_query,
                         rating=rating,
                         location=location,
                         mtype=mtype,
                         ctype=ctype,
                         stype=stype)

@app.route('/api/marketplace-products')
def get_marketplace_products():
    """API endpoint to fetch products with filters"""
    try:
        # Get filter parameters
        search = request.args.get('search', '').strip()
        rating = request.args.get('rating', '')
        location = request.args.get('location', '')
        mtype = request.args.get('mtype', '')
        ctype = request.args.get('ctype', '')
        stype = request.args.get('stype', '')
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        products = []
        
        # Build base conditions
        base_conditions = "isdeleted != 1 OR isdeleted IS NULL"
        search_condition = ""
        rating_condition = ""
        location_condition = ""
        
        # Search condition
        if search:
            search_condition = " AND LOWER(itemname) LIKE %s"
        
        # Rating condition
        if rating:
            rating_condition = f" AND itemrating >= {float(rating)}"
        
        # Location condition (join with business table)
        if location:
            location_condition = " AND b.primarylocation = %s"
        
        # Machinery query
        if not mtype or mtype in ['', 'all']:
            machinery_query = f"""
                SELECT m.itemid, m.itemname, m.item_price, m.itemdescription, 
                       m.quantityinstock, m.itemrating, m.date_created, m.image, 
                       m.issponsored, m.machinetype, 'machinery' as product_type,
                       b.businessname, b.primarylocation, b.businessrating
                FROM machinery m
                LEFT JOIN business b ON m.businessid = b.userid
                WHERE ({base_conditions}){search_condition}{rating_condition}{location_condition}
            """
        else:
            machinery_query = f"""
                SELECT m.itemid, m.itemname, m.item_price, m.itemdescription, 
                       m.quantityinstock, m.itemrating, m.date_created, m.image, 
                       m.issponsored, m.machinetype, 'machinery' as product_type,
                       b.businessname, b.primarylocation, b.businessrating
                FROM machinery m
                LEFT JOIN business b ON m.businessid = b.userid
                WHERE ({base_conditions}) AND m.machinetype = %s{search_condition}{rating_condition}{location_condition}
            """
        
        # Chemical query
        if not ctype or ctype in ['', 'all']:
            chemical_query = f"""
                SELECT c.itemid, c.itemname, c.item_price, c.itemdescription, 
                       c.quantityinstock, c.itemrating, c.date_created, c.image, 
                       c.issponsored, c.chemical_type, 'chemical' as product_type,
                       b.businessname, b.primarylocation, b.businessrating
                FROM chemical c
                LEFT JOIN business b ON c.businessid = b.userid
                WHERE ({base_conditions}){search_condition}{rating_condition}{location_condition}
            """
        else:
            chemical_query = f"""
                SELECT c.itemid, c.itemname, c.item_price, c.itemdescription, 
                       c.quantityinstock, c.itemrating, c.date_created, c.image, 
                       c.issponsored, c.chemical_type, 'chemical' as product_type,
                       b.businessname, b.primarylocation, b.businessrating
                FROM chemical c
                LEFT JOIN business b ON c.businessid = b.userid
                WHERE ({base_conditions}) AND c.chemical_type = %s{search_condition}{rating_condition}{location_condition}
            """
        
        # Service query
        if not stype or stype in ['', 'all']:
            service_query = f"""
                SELECT s.itemid, s.itemname, s.item_price, s.itemdescription, 
                       0 as quantityinstock, s.itemrating, s.date_created, s.image, 
                       s.issponsored, s.servicetype, 'service' as product_type,
                       b.businessname, b.primarylocation, b.businessrating
                FROM service s
                LEFT JOIN business b ON s.businessid = b.userid
                WHERE ({base_conditions}){search_condition}{rating_condition}{location_condition}
            """
        else:
            service_query = f"""
                SELECT s.itemid, s.itemname, s.item_price, s.itemdescription, 
                       0 as quantityinstock, s.itemrating, s.date_created, s.image, 
                       s.issponsored, s.servicetype, 'service' as product_type,
                       b.businessname, b.primarylocation, b.businessrating
                FROM service s
                LEFT JOIN business b ON s.businessid = b.userid
                WHERE ({base_conditions}) AND s.servicetype = %s{search_condition}{rating_condition}{location_condition}
            """
        
        # Execute queries based on filters
        if not mtype or mtype in ['', 'all']:
            params = []
            if search:
                params.append(f"%{search.lower()}%")
            if location:
                params.append(location)
            cursor.execute(machinery_query, params)
            products.extend(cursor.fetchall())
        elif mtype:
            params = [mtype]
            if search:
                params.append(f"%{search.lower()}%")
            if location:
                params.append(location)
            cursor.execute(machinery_query, params)
            products.extend(cursor.fetchall())
        
        if not ctype or ctype in ['', 'all']:
            params = []
            if search:
                params.append(f"%{search.lower()}%")
            if location:
                params.append(location)
            cursor.execute(chemical_query, params)
            products.extend(cursor.fetchall())
        elif ctype:
            params = [ctype]
            if search:
                params.append(f"%{search.lower()}%")
            if location:
                params.append(location)
            cursor.execute(chemical_query, params)
            products.extend(cursor.fetchall())
        
        if not stype or stype in ['', 'all']:
            params = []
            if search:
                params.append(f"%{search.lower()}%")
            if location:
                params.append(location)
            cursor.execute(service_query, params)
            products.extend(cursor.fetchall())
        elif stype:
            params = [stype]
            if search:
                params.append(f"%{search.lower()}%")
            if location:
                params.append(location)
            cursor.execute(service_query, params)
            products.extend(cursor.fetchall())
        
        cursor.close()
        conn.close()
        
        # Process products for display
        processed_products = []
        product_reviews_get=ProductManager()
        for product in products:
            product_dict = dict(product)
            
            # Handle image data and REMOVE the original binary image field
            if product_dict.get('image'):
                try:
                    image_data = product_dict['image']
                    
                    if isinstance(image_data, str):
                        product_dict['image_url'] = f"data:image/jpeg;base64,{image_data}"
                    elif isinstance(image_data, (bytes, memoryview)):
                        if isinstance(image_data, memoryview):
                            image_bytes = image_data.tobytes()
                        else:
                            image_bytes = image_data
                        
                        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                        product_dict['image_url'] = f"data:image/jpeg;base64,{image_base64}"
                    else:
                        product_dict['image_url'] = '../static/images/product-placeholder.jpg'
                        
                except Exception as e:
                    print(f"Error processing image: {e}")
                    product_dict['image_url'] = '../static/images/product-placeholder.jpg'
            else:
                product_dict['image_url'] = '../static/images/product-placeholder.jpg'
            
            # IMPORTANT: Remove the original binary image data to prevent JSON serialization error
            product_dict.pop('image', None)
            reviews=product_reviews_get.get_product_reviews(product_dict['itemid'], product_dict['product_type'])
            review_average=0.0
            for review in reviews:
                review_dict = dict(review)
                if not review_dict.get('client_name'):
                    review_dict['client_name'] = 'Anonymous'
                review_average += review_dict.get('rating', 0.0)
            
            product_dict['itemrating']= review_average/len(reviews) if reviews else 0.0
            product_dict['itemrating'] = product_dict.get('itemrating') or 0.0
            product_dict['issponsored'] = product_dict.get('issponsored') or False
            
            processed_products.append(product_dict)
        
        # Sort by sponsored first, then by rating, then by date
        processed_products.sort(key=lambda x: (
            not x.get('issponsored', False),  # Sponsored first
            -(x.get('itemrating') or 0),      # Higher rating first
            -(hash(x.get('date_created', '')) if x.get('date_created') else 0)  # Newer first
        ))
        
        return jsonify({
            'success': True,
            'products': processed_products,
            'total_count': len(processed_products)
        })
        
    except Exception as e:
        print(f"Error fetching marketplace products: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch products',
            'products': []
        }), 500


@app.route('/HoneyBeeHaven/view_business')
def view_business():
    """Display business profile information"""
    try:
        # Get userid from query parameter
        user_id = request.args.get('userid')
        
        if not user_id:
            flash('Business ID is required', 'error')
            return redirect(url_for('index'))
        
        # Convert to integer
        try:
            user_id = int(user_id)
        except ValueError:
            flash('Invalid business ID', 'error')
            return redirect(url_for('index'))
        
        # Get business data from database
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT userid, name, email, address, primarylocation, businessname, 
                   contactinfo, bankaccountnumber, businessdescription, 
                   targetkeywords, businessrating, datejoined, image
            FROM business 
            WHERE userid = %s AND is_banned = FALSE
        """, (user_id,))
        
        business = cursor.fetchone()
        
        if not business:
            cursor.close()
            conn.close()
            flash('Business not found or has been removed', 'error')
            return redirect(url_for('index'))
        
        # Convert to dict for easier handling
        business_data = dict(business)
        
        # Handle image data
        if business_data.get('image'):
            business_data['image_base64'] = base64.b64encode(business_data['image']).decode('utf-8')
        
        # Format date joined
        if business_data.get('datejoined'):
            try:
                # Handle both string and datetime objects
                if isinstance(business_data['datejoined'], str):
                    # Try different date formats
                    for date_format in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y']:
                        try:
                            date_obj = datetime.strptime(business_data['datejoined'], date_format)
                            business_data['datejoined_formatted'] = date_obj.strftime('%B %Y')
                            break
                        except ValueError:
                            continue
                    else:
                        # If no format works, use the original string
                        business_data['datejoined_formatted'] = business_data['datejoined']
                else:
                    # It's already a datetime object
                    business_data['datejoined_formatted'] = business_data['datejoined'].strftime('%B %Y')
            except Exception as e:
                print(f"Error formatting date: {e}")
                business_data['datejoined_formatted'] = str(business_data['datejoined'])
        
        # Format rating
        if business_data.get('businessrating'):
            business_data['rating_formatted'] = f"{business_data['businessrating']:.1f}/5"
        else:
            business_data['rating_formatted'] = "No ratings yet"
        
        # Process target keywords
        if business_data.get('targetkeywords'):
            business_data['keywords_list'] = [kw.strip() for kw in business_data['targetkeywords'].split(',')]
        else:
            business_data['keywords_list'] = []
        
        cursor.close()
        conn.close()
        
        # Fixed template name (corrected spelling)
        return render_template('honeybeehaven/shared/ViewBusinessProfile.html', 
                             business=business_data)
        
    except Exception as e:
        print(f"Error viewing business profile: {e}")
        flash('An error occurred while loading the business profile', 'error')
        return redirect(url_for('index'))


# API endpoint to get business data (for AJAX requests)
@app.route('/api/business/<int:user_id>')
def get_business_data_api(user_id):
    """API endpoint to get business data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT userid, name, email, address, primarylocation, businessname, 
                   contactinfo, bankaccountnumber, businessdescription, 
                   targetkeywords, businessrating, datejoined
            FROM business 
            WHERE userid = %s AND is_banned = FALSE
        """, (user_id,))
        
        business = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not business:
            return jsonify({'error': 'Business not found'}), 404
        
        # Convert to dict and format data
        business_dict = dict(business)
        
        # Format date
        if business_dict.get('datejoined'):
            try:
                if isinstance(business_dict['datejoined'], str):
                    # Try different date formats
                    for date_format in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y']:
                        try:
                            date_obj = datetime.strptime(business_dict['datejoined'], date_format)
                            business_dict['datejoined_formatted'] = date_obj.strftime('%B %Y')
                            break
                        except ValueError:
                            continue
                    else:
                        business_dict['datejoined_formatted'] = business_dict['datejoined']
                else:
                    business_dict['datejoined_formatted'] = business_dict['datejoined'].strftime('%B %Y')
            except Exception as e:
                print(f"Error formatting date: {e}")
                business_dict['datejoined_formatted'] = str(business_dict['datejoined'])
        
        # Format rating
        if business_dict.get('businessrating'):
            business_dict['rating_formatted'] = f"{business_dict['businessrating']:.1f}/5"
        else:
            business_dict['rating_formatted'] = "No ratings yet"
        
        # Process keywords
        if business_dict.get('targetkeywords'):
            business_dict['keywords_list'] = [kw.strip() for kw in business_dict['targetkeywords'].split(',')]
        else:
            business_dict['keywords_list'] = []
        
        return jsonify(business_dict)
        
    except Exception as e:
        print(f"Error fetching business data: {e}")
        return jsonify({'error': 'Database error'}), 500


@app.route('/reportBusiness/<int:business_id>')
def report_business_form(business_id):
    """Display the report business form"""
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash('Please log in to report a business', 'error')
            return redirect(url_for('login'))
        
        # Get business information to display in the form
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT userid, businessname, name 
            FROM business 
            WHERE userid = %s
        """, (business_id,))
        
        business = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not business:
            flash('Business not found', 'error')
            return redirect(url_for('index'))
        
        business_data = {
            'businessid': business[0],
            'businessname': business[1],
            'admin_name': business[2]
        }
        
        return render_template('honeybeehaven/client/reportBusiness.html', 
                             business=business_data)
    
    except Exception as e:
        print(f"Error loading report form: {e}")
        flash('An error occurred while loading the report form', 'error')
        return redirect(url_for('index'))


@app.route('/reportClient/<int:client_id>')
def report_client_form(client_id):
    """Display the report business form"""
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash('Please log in to report a client', 'error')
            return redirect(url_for('login'))
        
        # Get business information to display in the form
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT userid, email, name 
            FROM client 
            WHERE userid = %s
        """, (client_id,))
        
        client = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not client:
            flash('client not found', 'error')
            return redirect(url_for('index'))
        
        client_data = {
            'clientid': client[0],
            'clientemail': client[1],
            'client_name': client[2]
        }
        
        return render_template('honeybeehaven/business/reportClient.html', 
                             client=client_data)
    
    except Exception as e:
        print(f"Error loading report form: {e}")
        flash('An error occurred while loading the report form', 'error')
        return redirect(url_for('index'))


@app.route('/submitReportBusiness', methods=['POST'])
def submit_report_business():
    """Handle business report submission"""
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Please log in to report a business'}), 401
        
        # Get form data
        report_type = request.form.get('reportType', '').strip()
        report_reason = request.form.get('reportreason', '').strip()
        complainee_id = request.form.get('complaineeid', '').strip()
        
        # Validate input
        if not report_type:
            return jsonify({'success': False, 'message': 'Please select a report type'}), 400
        
        if not report_reason:
            return jsonify({'success': False, 'message': 'Please provide a reason for the report'}), 400
        
        if not complainee_id or not complainee_id.isdigit():
            return jsonify({'success': False, 'message': 'Invalid business ID'}), 400
        
        complainee_id = int(complainee_id)
        complainer_id = session['user_id']
        
        # Check if business exists
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT userid FROM business WHERE userid = %s", (complainee_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Business not found'}), 404
        
        # Check if user has already reported this business
        cursor.execute("""
            SELECT report3id FROM reported_business 
            WHERE complainee3id = %s AND complainer3id = %s
        """, (complainee_id, complainer_id))
        
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'You have already reported this business'}), 409
        
        # Insert the report
        cursor.execute("""
            INSERT INTO reported_business (complainee3id, complainer3id, report_reason3, report_type)
            VALUES (%s, %s, %s, %s)
            RETURNING report3id
        """, (complainee_id, complainer_id, report_reason, report_type))
        
        report_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        insert_notification(complainer_id,f'Your Report has been recevied. Thanks for letting us know.')
        return jsonify({
            'success': True, 
            'message': 'Report submitted successfully. Thank you for helping us maintain our community standards.',
            'report_id': report_id
        })
    
    except Exception as e:
        print(f"Error submitting business report: {e}")
        if 'conn' in locals():
            conn.rollback()
            cursor.close()
            conn.close()
        return jsonify({'success': False, 'message': 'An error occurred while submitting the report'}), 500

@app.route('/submitReportClient', methods=['POST'])
def submit_report_client():
    """Handle business report submission"""
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Please log in to report a business'}), 401
        
        # Get form data
        report_type = request.form.get('reportType', '').strip()
        report_reason = request.form.get('reportreason', '').strip()
        complainee_id = request.form.get('complaineeid', '').strip()
        
        # Validate input
        if not report_type:
            return jsonify({'success': False, 'message': 'Please select a report type'}), 400
        
        if not report_reason:
            return jsonify({'success': False, 'message': 'Please provide a reason for the report'}), 400
        
        if not complainee_id or not complainee_id.isdigit():
            return jsonify({'success': False, 'message': 'Invalid business ID'}), 400
        
        complainee_id = int(complainee_id)
        complainer_id = session['user_id']
        
        # Check if business exists
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT userid FROM client WHERE userid = %s", (complainee_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Client not found'}), 404
        
        # Check if user has already reported this business
        cursor.execute("""
            SELECT report2id FROM reported_clients
            WHERE complainee2id = %s AND complainer2id = %s
        """, (complainee_id, complainer_id))
        
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'You have already reported this client'}), 409
        
        # Insert the report
        cursor.execute("""
            INSERT INTO reported_clients (complainee2id, complainer2id, report_reason2, report_type)
            VALUES (%s, %s, %s, %s)
            RETURNING report2id
        """, (complainee_id, complainer_id, report_reason, report_type))
        
        report_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        insert_notification(complainer_id,f'Your Report has been recevied. Thanks for letting us know.')
        return jsonify({
            'success': True, 
            'message': 'Report submitted successfully. Thank you for helping us maintain our community standards.',
            'report_id': report_id
        })
    
    except Exception as e:
        print(f"Error submitting client report: {e}")
        if 'conn' in locals():
            conn.rollback()
            cursor.close()
            conn.close()
        return jsonify({'success': False, 'message': 'An error occurred while submitting the report'}), 500


@app.route('/api/check-report-status/<int:business_id>')
def check_report_status(business_id):
    """Check if current user has already reported this business"""
    try:
        if 'user_id' not in session:
            return jsonify({'can_report': False, 'message': 'Please log in'})
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT report3id FROM reported_business 
            WHERE complainee3id = %s AND complainer3id = %s
        """, (business_id, session['user_id']))
        
        already_reported = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        
        return jsonify({
            'can_report': not already_reported,
            'message': 'Already reported' if already_reported else 'Can report'
        })
    
    except Exception as e:
        print(f"Error checking report status: {e}")
        return jsonify({'can_report': True, 'message': 'Error checking status'})
    

@app.route('/api/check-report-status/client/<int:client_id>')
def check_report_status_client(client_id):
    """Check if current user has already reported this business"""
    try:
        if 'user_id' not in session:
            return jsonify({'can_report': False, 'message': 'Please log in'})
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT report2id FROM reported_clients 
            WHERE complainee2id = %s AND complainer2id = %s
        """, (client_id, session['user_id']))
        
        already_reported = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        
        return jsonify({
            'can_report': not already_reported,
            'message': 'Already reported' if already_reported else 'Can report'
        })
    
    except Exception as e:
        print(f"Error checking report status: {e}")
        return jsonify({'can_report': True, 'message': 'Error checking status'})
    

@app.route('/api/user-data_message')
def get_user_data():
    """Check if user is authenticated"""
    if 'user_id' in session:
        return jsonify({'authenticated': True, 'user_id': session['user_id']})
    return jsonify({'authenticated': False}), 401

def get_user_info(user_id, user_type):
    """Get user information based on user_id and type (client/business)"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if user_type == 'client':
            cur.execute("SELECT userid, name, email, image FROM client WHERE userid = %s", (user_id,))
        else:
            cur.execute("SELECT userid, name, email, image FROM business WHERE userid = %s", (user_id,))
        
        user = cur.fetchone()
        if user:
            user_dict = {
                'userid': user[0],
                'name': user[1],
                'email': user[2],
                'image': base64.b64encode(user[3]).decode('utf-8') if user[3] else None,
                'user_type': user_type  # Add user type to help with identification
            }
            return user_dict
        return None
    finally:
        cur.close()
        conn.close()

def get_or_create_conversation(user1_id, user2_id, user1_type, user2_type):
    """Get existing conversation or create new one"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Determine business and client IDs
        if user1_type == 'business':
            business_id, client_id = user1_id, user2_id
        else:
            business_id, client_id = user2_id, user1_id

        # Check if conversation exists
        cur.execute("""
            SELECT conversationid FROM conversation 
            WHERE businessid = %s AND clientid = %s
        """, (business_id, client_id))
        
        conversation = cur.fetchone()
        
        if conversation:
            return conversation[0]
        else:
            # Create new conversation
            cur.execute("""
                INSERT INTO conversation (businessid, clientid) 
                VALUES (%s, %s) RETURNING conversationid
            """, (business_id, client_id))
            conversation_id = cur.fetchone()[0]
            conn.commit()
            insert_notification(business_id,f'A conversation has been started with customer')
            insert_notification(client_id,f'A conversation has been started with buyer')
            return conversation_id
    finally:
        cur.close()
        conn.close()

def get_user_type_by_id(user_id):
    """Determine if a user_id belongs to business or client table"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Check if user exists in business table
        cur.execute("SELECT userid FROM business WHERE userid = %s", (user_id,))
        if cur.fetchone():
            return 'business'
        
        # Check if user exists in client table
        cur.execute("SELECT userid FROM client WHERE userid = %s", (user_id,))
        if cur.fetchone():
            return 'client'
        
        return None
    finally:
        cur.close()
        conn.close()

# Route to display all chats
@app.route('/chats')
def chats():
    """Display all conversations for the current user"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user_type = session.get('user_type', 'client')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get all conversations for the user
        if user_type == 'client':
            cur.execute("""
                SELECT c.conversationid, c.businessid, 
                       COALESCE(b.businessname, b.name) as business_name, 
                       b.name, b.image,
                       m.text as last_message, 
                       m.messageid as last_message_id,
                       m.timestamp as last_message_time
                FROM conversation c
                JOIN business b ON c.businessid = b.userid
                LEFT JOIN (
                    SELECT DISTINCT ON (conversationid) 
                           conversationid, text, messageid, timestamp
                    FROM message 
                    ORDER BY conversationid, messageid DESC
                ) m ON c.conversationid = m.conversationid
                WHERE c.clientid = %s
                ORDER BY COALESCE(m.messageid, 0) DESC, c.conversationid DESC
            """, (user_id,))
        else:
            cur.execute("""
                SELECT c.conversationid, c.clientid, 
                       cl.name as business_name, 
                       cl.name, cl.image,
                       m.text as last_message, 
                       m.messageid as last_message_id,
                       m.timestamp as last_message_time
                FROM conversation c
                JOIN client cl ON c.clientid = cl.userid
                LEFT JOIN (
                    SELECT DISTINCT ON (conversationid) 
                           conversationid, text, messageid, timestamp
                    FROM message 
                    ORDER BY conversationid, messageid DESC
                ) m ON c.conversationid = m.conversationid
                WHERE c.businessid = %s
                ORDER BY COALESCE(m.messageid, 0) DESC, c.conversationid DESC
            """, (user_id,))
        
        conversations = cur.fetchall()
        
        # Format conversations for template
        chat_list = []
        for conv in conversations:
            chat_info = {
                'conversation_id': conv[0],
                'other_user_id': conv[1],
                'business_name': conv[2],
                'user_name': conv[3],
                'image': base64.b64encode(conv[4]).decode('utf-8') if conv[4] else None,
                'last_message': conv[5] if conv[5] else 'No messages yet'
            }
            chat_list.append(chat_info)
        
        return render_template('honeybeehaven/shared/chat.html', chats=chat_list)
    
    finally:
        cur.close()
        conn.close()

# Route to display inbox/chat interface
@app.route('/inbox')
@app.route('/inbox/<int:conversation_id>')
def inbox(conversation_id=None):
    """Display chat interface"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user_type = session.get('user_type', 'client')
    
    if not conversation_id:
        return redirect(url_for('chats'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Verify user has access to this conversation
        cur.execute("""
            SELECT businessid, clientid FROM conversation 
            WHERE conversationid = %s AND (businessid = %s OR clientid = %s)
        """, (conversation_id, user_id, user_id))
        
        conversation = cur.fetchone()
        if not conversation:
            flash('Conversation not found or access denied.')
            return redirect(url_for('chats'))
        
        business_id, client_id = conversation
        
        # Determine other user info based on current user type
        if user_type == 'client':
            other_user_id = business_id
            other_user_type = 'business'
        else:
            other_user_id = client_id
            other_user_type = 'client'
        
        # Get other user info
        other_user = get_user_info(other_user_id, other_user_type)
        
        # Get messages with proper sender identification
        cur.execute("""
            SELECT m.messageid, m.senderid, m.receiverid, m.text, m.timestamp,
                   CASE 
                       WHEN m.senderid = %s THEN 'You'
                       WHEN m.senderid = c.businessid THEN COALESCE(b.businessname, b.name)
                       WHEN m.senderid = c.clientid THEN cl.name
                       ELSE 'Unknown'
                   END as sender_name,
                   CASE 
                       WHEN m.senderid = %s THEN NULL
                       WHEN m.senderid = c.businessid THEN b.image
                       WHEN m.senderid = c.clientid THEN cl.image
                       ELSE NULL
                   END as sender_image,
                   CASE 
                       WHEN m.senderid = c.businessid THEN 'business'
                       WHEN m.senderid = c.clientid THEN 'client'
                       ELSE 'unknown'
                   END as sender_type
            FROM message m
            JOIN conversation c ON m.conversationid = c.conversationid
            LEFT JOIN business b ON c.businessid = b.userid
            LEFT JOIN client cl ON c.clientid = cl.userid
            WHERE m.conversationid = %s
            ORDER BY m.messageid ASC
        """, (user_id, user_id, conversation_id))
        
        messages = cur.fetchall()
        
        # Format messages
        message_list = []
        for msg in messages:
            message_info = {
                'messageid': msg[0],
                'senderid': msg[1],
                'receiverid': msg[2],
                'text': msg[3],
                'timestamp': msg[4],
                'sender_name': msg[5],
                'sender_image': base64.b64encode(msg[6]).decode('utf-8') if msg[6] else None,
                'sender_type': msg[7],
                'is_own_message': msg[1] == user_id
            }
            message_list.append(message_info)
        
        return render_template('honeybeehaven/shared/inbox.html', 
                             messages=message_list, 
                             conversation_id=conversation_id,
                             other_user=other_user,
                             other_user_id=other_user_id)
    
    finally:
        cur.close()
        conn.close()

# Route to send message
@app.route('/send_message', methods=['POST'])
def send_message():
    """Send a message"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please log in to send messages.'})
    
    user_id = session['user_id']
    user_type = session.get('user_type', 'client')
    conversation_id = request.form.get('conversation_id')
    other_user_id = request.form.get('other_user_id')
    message_text = request.form.get('message_text', '').strip()
    
    if not conversation_id or not other_user_id or not message_text:
        return jsonify({'success': False, 'message': 'Missing required information.'})
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Verify conversation access and get conversation details
        cur.execute("""
            SELECT businessid, clientid FROM conversation 
            WHERE conversationid = %s AND (businessid = %s OR clientid = %s)
        """, (conversation_id, user_id, user_id))
        
        conversation = cur.fetchone()
        if not conversation:
            return jsonify({'success': False, 'message': 'Access denied.'})
        
        business_id, client_id = conversation
        
        # Determine the correct receiver based on conversation structure
        if user_type == 'client' and user_id == client_id:
            receiver_id = business_id
        elif user_type == 'business' and user_id == business_id:
            receiver_id = client_id
        else:
            return jsonify({'success': False, 'message': 'Invalid user access to conversation.'})
        
        # Insert message with proper sender and receiver
        cur.execute("""
            INSERT INTO message (conversationid, senderid, receiverid, text, timestamp)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING messageid, timestamp
        """, (conversation_id, user_id, receiver_id, message_text))
        
        result = cur.fetchone()
        message_id, timestamp = result
        conn.commit()
        
        # Return success with message info
        return jsonify({
            'success': True,
            'message_id': message_id,
            'sender_name': 'You',
            'text': message_text,
            'timestamp': timestamp.isoformat() if timestamp else None
        })
    
    except Exception as e:
        conn.rollback()
        print(f"Error sending message: {e}")
        return jsonify({'success': False, 'message': 'Error sending message.'})
    
    finally:
        cur.close()
        conn.close()

# API route to get new messages (for real-time updates)
@app.route('/api/messages/<int:conversation_id>/<int:last_message_id>')
def get_new_messages(conversation_id, last_message_id):
    """Get new messages since last_message_id"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'})
    
    user_id = session['user_id']
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Verify access
        cur.execute("""
            SELECT businessid, clientid FROM conversation 
            WHERE conversationid = %s AND (businessid = %s OR clientid = %s)
        """, (conversation_id, user_id, user_id))
        
        conversation = cur.fetchone()
        if not conversation:
            return jsonify({'success': False, 'message': 'Access denied'})
        
        # Get new messages with proper sender identification
        cur.execute("""
            SELECT m.messageid, m.senderid, m.receiverid, m.text, m.timestamp,
                   CASE 
                       WHEN m.senderid = %s THEN 'You'
                       WHEN m.senderid = c.businessid THEN COALESCE(b.businessname, b.name)
                       WHEN m.senderid = c.clientid THEN cl.name
                       ELSE 'Unknown'
                   END as sender_name,
                   CASE 
                       WHEN m.senderid = %s THEN NULL
                       WHEN m.senderid = c.businessid THEN b.image
                       WHEN m.senderid = c.clientid THEN cl.image
                       ELSE NULL
                   END as sender_image,
                   CASE 
                       WHEN m.senderid = c.businessid THEN 'business'
                       WHEN m.senderid = c.clientid THEN 'client'
                       ELSE 'unknown'
                   END as sender_type
            FROM message m
            JOIN conversation c ON m.conversationid = c.conversationid
            LEFT JOIN business b ON c.businessid = b.userid
            LEFT JOIN client cl ON c.clientid = cl.userid
            WHERE m.conversationid = %s AND m.messageid > %s
            ORDER BY m.messageid ASC
        """, (user_id, user_id, conversation_id, last_message_id))
        
        messages = cur.fetchall()
        
        # Format messages
        new_messages = []
        for msg in messages:
            message_info = {
                'messageid': msg[0],
                'senderid': msg[1],
                'receiverid': msg[2],
                'text': msg[3],
                'timestamp': msg[4].isoformat() if msg[4] else None,
                'sender_name': msg[5],
                'sender_image': base64.b64encode(msg[6]).decode('utf-8') if msg[6] else None,
                'sender_type': msg[7],
                'is_own_message': msg[1] == user_id
            }
            new_messages.append(message_info)
        
        return jsonify({'success': True, 'messages': new_messages})
    
    finally:
        cur.close()
        conn.close()

@app.route('/api/conversation/<int:conversation_id>')
def get_conversation_details(conversation_id):
    """Get conversation details and messages"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    user_type = session.get('user_type', 'client')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Verify access and get conversation details
        cur.execute("""
            SELECT businessid, clientid FROM conversation 
            WHERE conversationid = %s AND (businessid = %s OR clientid = %s)
        """, (conversation_id, user_id, user_id))
        
        conversation = cur.fetchone()
        if not conversation:
            return jsonify({'success': False, 'message': 'Conversation not found or access denied'})
        
        business_id, client_id = conversation
        
        # Determine other user info based on current user type
        if user_type == 'client':
            other_user_id = business_id
            other_user_type = 'business'
        else:
            other_user_id = client_id
            other_user_type = 'client'
        
        # Get other user info
        other_user = get_user_info(other_user_id, other_user_type)
        if not other_user:
            return jsonify({'success': False, 'message': 'Other user not found'})
        
        # Get messages with proper sender identification
        cur.execute("""
            SELECT m.messageid, m.senderid, m.receiverid, m.text, m.timestamp,
                   CASE 
                       WHEN m.senderid = %s THEN 'You'
                       WHEN m.senderid = c.businessid THEN COALESCE(b.businessname, b.name)
                       WHEN m.senderid = c.clientid THEN cl.name
                       ELSE 'Unknown'
                   END as sender_name,
                   CASE 
                       WHEN m.senderid = %s THEN NULL
                       WHEN m.senderid = c.businessid THEN b.image
                       WHEN m.senderid = c.clientid THEN cl.image
                       ELSE NULL
                   END as sender_image,
                   CASE 
                       WHEN m.senderid = c.businessid THEN 'business'
                       WHEN m.senderid = c.clientid THEN 'client'
                       ELSE 'unknown'
                   END as sender_type
            FROM message m
            JOIN conversation c ON m.conversationid = c.conversationid
            LEFT JOIN business b ON c.businessid = b.userid
            LEFT JOIN client cl ON c.clientid = cl.userid
            WHERE m.conversationid = %s
            ORDER BY m.messageid ASC
        """, (user_id, user_id, conversation_id))
        
        messages = cur.fetchall()
        
        # Format messages
        message_list = []
        for msg in messages:
            message_info = {
                'messageid': msg[0],
                'senderid': msg[1],
                'receiverid': msg[2],
                'text': msg[3],
                'timestamp': msg[4].isoformat() if msg[4] else None,
                'sender_name': msg[5],
                'sender_image': base64.b64encode(msg[6]).decode('utf-8') if msg[6] else None,
                'sender_type': msg[7],
                'is_own_message': msg[1] == user_id
            }
            message_list.append(message_info)
        
        return jsonify({
            'success': True,
            'other_user_id': other_user_id,
            'other_user': other_user,
            'messages': message_list
        })
    
    except Exception as e:
        print(f"Error in get_conversation_details: {e}")
        return jsonify({'success': False, 'message': 'Server error occurred'}), 500
    
    finally:
        cur.close()
        conn.close()

@app.route('/start_conversation/<int:business_id>', methods=['GET'])
def start_conversation(business_id):
    """Start conversation with a business"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please log in to send messages.'}), 401
    
    user_id = session['user_id']
    user_type = session.get('user_type', 'client')
    
    # Prevent users from messaging themselves
    if user_type == 'business' and user_id == business_id:
        return jsonify({'success': False, 'message': 'You cannot send messages to yourself.'}), 400
    
    try:
        # Get or create conversation
        conversation_id = get_or_create_conversation(user_id, business_id, user_type, 'business')
        
        # Redirect to inbox with conversation
        return redirect(url_for('inbox', conversation_id=conversation_id))
    
    except Exception as e:
        print(f"Error starting conversation: {e}")
        return jsonify({'success': False, 'message': 'Error starting conversation'}), 500


@app.route('/start_conversation/client/<int:client_id>', methods=['GET'])
def start_conversation_client(client_id):
    """Start conversation with a business"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please log in to send messages.'}), 401
    
    user_id = session['user_id']
    user_type = session.get('user_type', 'business')
    
    # Prevent users from messaging themselves
    if user_type == 'client' and user_id == client_id:
        return jsonify({'success': False, 'message': 'You cannot send messages to yourself.'}), 400
    
    try:
        # Get or create conversation
        conversation_id = get_or_create_conversation(user_id, client_id, user_type, 'client')
        
        # Redirect to inbox with conversation
        return redirect(url_for('inbox', conversation_id=conversation_id))
    
    except Exception as e:
        print(f"Error starting conversation: {e}")
        return jsonify({'success': False, 'message': 'Error starting conversation'}), 500




@app.route('/api/user-chats')
def get_user_chats():
    """API endpoint to get user's conversations"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    user_type = session.get('user_type', 'client')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get all conversations for the user with proper ordering
        if user_type == 'client':
            cur.execute("""
                WITH latest_messages AS (
                    SELECT DISTINCT ON (conversationid) 
                           conversationid, text, messageid, timestamp
                    FROM message 
                    ORDER BY conversationid, messageid DESC
                )
                SELECT c.conversationid, c.businessid, 
                       COALESCE(b.businessname, b.name) as business_name, 
                       b.name, b.image,
                       COALESCE(lm.text, 'No messages yet') as last_message,
                       COALESCE(lm.messageid, 0) as last_message_id
                FROM conversation c
                JOIN business b ON c.businessid = b.userid
                LEFT JOIN latest_messages lm ON c.conversationid = lm.conversationid
                WHERE c.clientid = %s
                ORDER BY COALESCE(lm.messageid, 0) DESC, c.conversationid DESC
            """, (user_id,))
        else:
            cur.execute("""
                WITH latest_messages AS (
                    SELECT DISTINCT ON (conversationid) 
                           conversationid, text, messageid, timestamp
                    FROM message 
                    ORDER BY conversationid, messageid DESC
                )
                SELECT c.conversationid, c.clientid, 
                       cl.name as business_name, 
                       cl.name, cl.image,
                       COALESCE(lm.text, 'No messages yet') as last_message,
                       COALESCE(lm.messageid, 0) as last_message_id
                FROM conversation c
                JOIN client cl ON c.clientid = cl.userid
                LEFT JOIN latest_messages lm ON c.conversationid = lm.conversationid
                WHERE c.businessid = %s
                ORDER BY COALESCE(lm.messageid, 0) DESC, c.conversationid DESC
            """, (user_id,))
        
        conversations = cur.fetchall()
        
        # Format conversations for JSON response
        chat_list = []
        for conv in conversations:
            chat_info = {
                'conversation_id': conv[0],
                'other_user_id': conv[1],
                'business_name': conv[2],
                'user_name': conv[3],
                'image': base64.b64encode(conv[4]).decode('utf-8') if conv[4] else None,
                'last_message': conv[5]
            }
            chat_list.append(chat_info)
        
        return jsonify({'success': True, 'chats': chat_list})
    
    except Exception as e:
        print(f"Error getting user chats: {e}")
        return jsonify({'success': False, 'message': 'Error loading chats'}), 500
    
    finally:
        cur.close()
        conn.close()


@app.route('/HoneyBeeHaven/addreview')
def add_review():
    """Display the add review form"""
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please log in to write a review', 'error')
        return redirect(url_for('login'))
    
    # Check if user is a client (not business)
    if session.get('user_type') != 'client':
        flash('Only clients can write reviews', 'error')
        return redirect(url_for('index'))
    
    # Get item ID and item type from URL parameters
    item_id = request.args.get('itemid')
    item_type = request.args.get('itemtype', 'chemical')  # Default to chemical if not specified
    
    if not item_id:
        flash('Invalid item ID', 'error')
        return redirect(url_for('index'))
    
    try:
        # Verify the item exists in the appropriate table
        conn = get_db_connection()
        cur = conn.cursor()
        
        item = None
        if item_type == 'chemical':
            cur.execute("SELECT itemname FROM chemical WHERE itemid = %s AND isdeleted = 0", (item_id,))
            item = cur.fetchone()
        elif item_type == 'service':
            cur.execute("SELECT itemname FROM service WHERE itemid = %s AND isdeleted = 0", (item_id,))
            item = cur.fetchone()
        elif item_type == 'machinery':
            cur.execute("SELECT itemname FROM machinery WHERE itemid = %s AND isdeleted = 0", (item_id,))
            item = cur.fetchone()
        else:
            flash('Invalid item type', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('index'))
        
        cur.close()
        conn.close()
        
        if not item:
            flash('Item not found', 'error')
            return redirect(url_for('index'))
        
        # Pass item details to the template
        return render_template('honeybeehaven/client/review.html', 
                             item_id=item_id, 
                             item_name=item[0], 
                             item_type=item_type)
        
    except Exception as e:
        print(f"Error loading review form: {e}")
        flash('Error loading review form', 'error')
        return redirect(url_for('index'))





@app.route('/HoneyBeeHaven/submitreview', methods=['POST'])
def submit_review():
    """Handle review submission"""
    try:
        # Check if user is logged in and is a client
        if 'user_id' not in session:
            return jsonify({'error': 'Please log in to submit a review'}), 401
        
        if session.get('user_type') != 'client':
            return jsonify({'error': 'Only clients can write reviews'}), 403
        
        # Get form data
        title = request.form.get('title', '').strip()
        rating = request.form.get('rating')
        text = request.form.get('text', '').strip()
        item_id = request.form.get('itemid')
        item_type = request.form.get('itemtype', 'chemical')
        
        # Validate required fields
        if not all([title, rating, text, item_id]):
            flash('All fields are required', 'error')
            return redirect(url_for('add_review', itemid=item_id, itemtype=item_type))
        
        # Validate rating range
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                flash('Rating must be between 1 and 5', 'error')
                return redirect(url_for('add_review', itemid=item_id, itemtype=item_type))
        except ValueError:
            flash('Invalid rating value', 'error')
            return redirect(url_for('add_review', itemid=item_id, itemtype=item_type))
        
        # Validate item exists in the appropriate table
        conn = get_db_connection()
        cur = conn.cursor()
        
        item_exists = False
        if item_type == 'chemical':
            cur.execute("SELECT itemid FROM chemical WHERE itemid = %s AND isdeleted = 0", (item_id,))
            item_exists = cur.fetchone() is not None
        elif item_type == 'service':
            cur.execute("SELECT itemid FROM service WHERE itemid = %s AND isdeleted = 0", (item_id,))
            item_exists = cur.fetchone() is not None
        elif item_type == 'machinery':
            cur.execute("SELECT itemid FROM machinery WHERE itemid = %s AND isdeleted = 0", (item_id,))
            item_exists = cur.fetchone() is not None
        
        if not item_exists:
            flash('Invalid item', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('index'))
        
        # Check if user already reviewed this item
        cur.execute("""
            SELECT reviewid FROM review 
            WHERE clientid = %s AND itemid = %s AND producttype = %s
        """, (session['user_id'], item_id,item_type))
        
        if cur.fetchone():
            flash('You have already reviewed this item', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('add_review', itemid=item_id, itemtype=item_type))
        
        # Insert the review
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cur.execute("""
            INSERT INTO review (clientid, date, itemid, rating, text, title,producttype)
            VALUES (%s, %s, %s, %s, %s, %s,%s)
            RETURNING reviewid
        """, (session['user_id'], current_date, item_id, rating, text, title,item_type))
        
        review_id = cur.fetchone()[0]
        conn.commit()
        
        # Update the item rating in the appropriate table
        update_item_rating(cur, item_id, item_type)
        conn.commit()
        
        cur.close()
        conn.close()
        
        flash('Review submitted successfully!', 'success')
        return redirect(url_for('view_product', id=item_id, type=item_type))
        
    except Exception as e:
        print(f"Error submitting review: {e}")
        flash('Error submitting review. Please try again.', 'error')
        return redirect(url_for('add_review', itemid=request.form.get('itemid'), itemtype=request.form.get('itemtype')))


def update_item_rating(cursor, item_id, item_type):
    """Update the average rating for an item"""
    try:
        # Calculate new average rating
        cursor.execute("""
            SELECT AVG(rating::numeric) FROM review WHERE itemid = %s
        """, (item_id,))
        
        avg_rating = cursor.fetchone()[0]
        if avg_rating is not None:
            avg_rating = round(float(avg_rating), 2)
        else:
            avg_rating = 0.0
        
        # Update the appropriate table
        if item_type == 'chemical':
            cursor.execute("""
                UPDATE chemical SET itemrating = %s WHERE itemid = %s
            """, (avg_rating, item_id))
        elif item_type == 'service':
            cursor.execute("""
                UPDATE service SET itemrating = %s WHERE itemid = %s
            """, (avg_rating, item_id))
        elif item_type == 'machinery':
            cursor.execute("""
                UPDATE machinery SET itemrating = %s WHERE itemid = %s
            """, (avg_rating, item_id))
            
    except Exception as e:
        print(f"Error updating item rating: {e}")


@app.route('/HoneyBeeHaven/reportreview')
def report_review():
    """Display the report review form"""
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please log in to report a review', 'error')
        return redirect(url_for('login'))
    
    # Get review ID from URL parameter
    review_id = request.args.get('reviewid')
    if not review_id:
        flash('Invalid review ID', 'error')
        return redirect(url_for('index'))
    
    try:
        # Get review details
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT r.reviewid, r.clientid, r.title, r.text, c.name as reviewer_name, r.itemid
            FROM review r
            JOIN client c ON r.clientid = c.userid
            WHERE r.reviewid = %s
        """, (review_id,))
        
        review = cur.fetchone()
        cur.close()
        conn.close()
        
        if not review:
            flash('Review not found', 'error')
            return redirect(url_for('index'))
        
        # Check if user is trying to report their own review
        if review[1] == session['user_id']:
            flash('You cannot report your own review', 'error')
            return redirect(url_for('index'))
        
        review_data = {
            'reviewid': review[0],
            'complaineeid': review[1],  # The person who wrote the review
            'title': review[2],
            'text': review[3],
            'reviewer_name': review[4],
            'itemid': review[5]
        }
        
        return render_template('honeybeehaven/business/reportReview.html', review=review_data)
        
    except Exception as e:
        print(f"Error loading report form: {e}")
        flash('Error loading report form', 'error')
        return redirect(url_for('index'))


@app.route('/HoneyBeeHaven/submitreportReview', methods=['POST'])
def submit_report_review():
    """Handle review report submission"""
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            return jsonify({'error': 'Please log in to report a review'}), 401
        
        # Get form data
        report_type = request.form.get('reportType', '').strip()
        report_reason = request.form.get('reportreason', '').strip()
        review_id = request.form.get('reviewid')
        complainee_id = request.form.get('complaineeid')  # The person who wrote the review
        review_content = request.form.get('reviewcontent', '').strip()
        
        # Validate required fields
        if not all([report_type, report_reason, review_id, complainee_id]):
            flash('All fields are required', 'error')
            return redirect(url_for('report_review', reviewid=review_id))
        
        # Validate report type
        valid_report_types = [
            'discrimination', 'hateSpeech', 'abuseViolence', 
            'harassment', 'fraudScam', 'inappropriateContent', 'misinformation'
        ]
        if report_type not in valid_report_types:
            flash('Invalid report type', 'error')
            return redirect(url_for('report_review', reviewid=review_id))
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verify the review exists and get review content if not provided
        cur.execute("""
            SELECT clientid, text, title FROM review WHERE reviewid = %s
        """, (review_id,))
        review_data = cur.fetchone()
        
        if not review_data:
            flash('Review not found', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('index'))
        
        # Use review content from database if not provided in form
        if not review_content:
            review_content = f"{review_data[2]}: {review_data[1]}"  # title: text
        
        # Truncate review content if it's too long (database field is varchar(255))
        if len(review_content) > 255:
            review_content = review_content[:252] + "..."
        
        # Check if user already reported this review
        cur.execute("""
            SELECT reportid FROM reported_reviews 
            WHERE complainerid = %s AND reviewid = %s
        """, (session['user_id'], review_id))
        
        if cur.fetchone():
            flash('You have already reported this review', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('index'))
        
        # Insert the report
        cur.execute("""
            INSERT INTO reported_reviews 
            (complaineeid, complainerid, report_reason, report_type, review_content, reviewid)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING reportid
        """, (complainee_id, session['user_id'], report_reason, report_type, review_content, review_id))
        
        report_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        insert_notification(session['user_id'],f'Your Report has been recevied. Thanks for letting us know.')
        flash('Review reported successfully. Our team will review it shortly.', 'success')
        return redirect(url_for('index'))  # Redirect to home page
        
    except Exception as e:
        print(f"Error submitting report: {e}")
        flash('Error submitting report. Please try again.', 'error')
        return redirect(url_for('report_review', reviewid=request.form.get('reviewid')))


# Helper function to get item details from any of the three tables
def get_item_details(item_id, item_type=None):
    """Get item details from chemical, service, or machinery tables"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        item = None
        actual_type = None
        
        if item_type:
            # If item_type is specified, check only that table
            if item_type == 'chemical':
                cur.execute("SELECT itemname, item_price, itemdescription FROM chemical WHERE itemid = %s AND isdeleted = 0", (item_id,))
                item = cur.fetchone()
                actual_type = 'chemical' if item else None
            elif item_type == 'service':
                cur.execute("SELECT itemname, item_price, itemdescription FROM service WHERE itemid = %s AND isdeleted = 0", (item_id,))
                item = cur.fetchone()
                actual_type = 'service' if item else None
            elif item_type == 'machinery':
                cur.execute("SELECT itemname, item_price, itemdescription FROM machinery WHERE itemid = %s AND isdeleted = 0", (item_id,))
                item = cur.fetchone()
                actual_type = 'machinery' if item else None
        else:
            # If item_type is not specified, check all tables
            for table_type in ['chemical', 'service', 'machinery']:
                cur.execute(f"SELECT itemname, item_price, itemdescription FROM {table_type} WHERE itemid = %s AND isdeleted = 0", (item_id,))
                item = cur.fetchone()
                if item:
                    actual_type = table_type
                    break
        
        cur.close()
        conn.close()
        
        if item:
            return {
                'itemname': item[0],
                'item_price': item[1],
                'itemdescription': item[2],
                'itemtype': actual_type
            }
        return None
        
    except Exception as e:
        print(f"Error getting item details: {e}")
        return None






@app.route('/BeeKeeper/')
def admin_login():
    return render_template('beekeeper/index.html')

@app.route('/BeeKeeper/logindata', methods=['POST'])
def admin_login_data():
    email = request.form['email']
    password = request.form['password']
    
    conn = get_db_connection()
    cur = conn.cursor()
    # Insert new admin
    
    try:
        cur.execute("SELECT adminid, admin_name, admin_password FROM admin2 WHERE admin_email = %s", (email,))
        admin = cur.fetchone()
        
        if admin and admin[2] == password:  # Simple password check - consider using bcrypt
            session['admin_id'] = admin[0]
            session['admin_name'] = admin[1]
            session['admin_email'] = email
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials')
            return redirect(url_for('admin_login'))
    finally:
        cur.close()
        conn.close()

# Update your existing admin_dashboard function to handle the tojson filter
@app.route('/BeeKeeper/AdminDashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Total users
        cur.execute("SELECT COUNT(*) FROM client WHERE NOT is_banned")
        total_clients = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM business WHERE NOT is_banned")
        total_businesses = cur.fetchone()[0]
        
        # Monthly registrations - fixed query
        cur.execute("""
            SELECT 
                EXTRACT(MONTH FROM TO_DATE(datejoined, 'YYYY-MM-DD')) as month,
                COUNT(*) as count
            FROM client 
            WHERE datejoined IS NOT NULL 
              AND datejoined ~ '^\d{4}-\d{2}-\d{2}$'
              AND EXTRACT(YEAR FROM TO_DATE(datejoined, 'YYYY-MM-DD')) = EXTRACT(YEAR FROM CURRENT_DATE)
            GROUP BY month
            ORDER BY month
        """)
        client_monthly = cur.fetchall()
        
        cur.execute("""
            SELECT 
                EXTRACT(MONTH FROM TO_DATE(datejoined, 'YYYY-MM-DD')) as month,
                COUNT(*) as count
            FROM business 
            WHERE datejoined IS NOT NULL 
              AND datejoined ~ '^\d{4}-\d{2}-\d{2}$'
              AND EXTRACT(YEAR FROM TO_DATE(datejoined, 'YYYY-MM-DD')) = EXTRACT(YEAR FROM CURRENT_DATE)
            GROUP BY month
            ORDER BY month
        """)
        business_monthly = cur.fetchall()
        
        # Location statistics
        cur.execute("""
            SELECT primarylocation, COUNT(*) as count
            FROM (
                SELECT primarylocation FROM client WHERE primarylocation IS NOT NULL
                UNION ALL
                SELECT primarylocation FROM business WHERE primarylocation IS NOT NULL
            ) as locations
            GROUP BY primarylocation
            ORDER BY count DESC
            LIMIT 5
        """)
        location_stats = cur.fetchall()
        
        # Revenue statistics
        cur.execute("""
            SELECT 
                EXTRACT(YEAR FROM orderdate) as year,
                SUM(COALESCE(honeybeehavencommision, 0)) as revenue
            FROM order_table
            WHERE orderdate >= CURRENT_DATE - INTERVAL '5 years'
            GROUP BY year
            ORDER BY year
        """)
        revenue_stats = cur.fetchall()
        
        # Subscription statistics
        cur.execute("""
            SELECT subtype, COUNT(*) as count
            FROM subscription
            WHERE NOT COALESCE(expired, false)
            GROUP BY subtype
        """)
        subscription_stats = cur.fetchall()
        
        stats = {
            'total_clients': total_clients,
            'total_businesses': total_businesses,
            'client_monthly': client_monthly,
            'business_monthly': business_monthly,
            'location_stats': location_stats,
            'revenue_stats': revenue_stats,
            'subscription_stats': subscription_stats
        }
        
        return render_template('beekeeper/admin/dashboard.html', stats=stats, admin_name=session['admin_name'])
    finally:
        cur.close()
        conn.close()


@app.route('/BeeKeeper/contact')
def contacts():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT name, email, subject, message FROM contact ORDER BY name")
        contacts = cur.fetchall()
        return render_template('beekeeper/admin/contacts.html', contacts=contacts)
    finally:
        cur.close()
        conn.close()

@app.route('/BeeKeeper/AdminReports')
def admin_reports():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT reportid, complainerid, complaineeid, report_reason, 
                   reviewid, review_content, report_type
            FROM reported_reviews
            ORDER BY reportid DESC
        """)
        reports = cur.fetchall()
        return render_template('beekeeper/admin/all-reports.html', reports=reports)
    finally:
        cur.close()
        conn.close()

@app.route('/BeeKeeper/ReportedClients')
def reported_clients():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT report2id, complainer2id, complainee2id, report_reason2, report_type
            FROM reported_clients
            ORDER BY report2id DESC
        """)
        reports = cur.fetchall()
        return render_template('beekeeper/admin/reported-clients.html', reports=reports)
    finally:
        cur.close()
        conn.close()

@app.route('/BeeKeeper/ReportedBusiness')
def reported_business():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT report3id, complainer3id, complainee3id, report_reason3, report_type
            FROM reported_business
            ORDER BY report3id DESC
        """)
        reports = cur.fetchall()
        return render_template('beekeeper/admin/reported-business.html', reports=reports)
    finally:
        cur.close()
        conn.close()

@app.route('/BeeKeeper/Subscriptions')
def subscriptions():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT s.subscriptionid, b.businessname, b.email, s.subtype, 
                   s.startdate, s.enddate, s.expired, s.sponsored_products_limit,
                   s.sponsored_products_used
            FROM subscription s
            JOIN business b ON s.businessid = b.userid
            ORDER BY s.subscriptionid DESC
        """)
        
        subscriptions = cur.fetchall()
        print(subscriptions)
        return render_template('beekeeper/admin/subscriptions.html', subscriptions=subscriptions)
    finally:
        cur.close()
        conn.close()

@app.route('/BeeKeeper/ban_client', methods=['POST'])
def ban_client():
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    client_id = request.json.get('client_id')
    ban_duration = request.json.get('ban_duration')
    ban_unit = request.json.get('ban_unit')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        if ban_duration == 'permanent':
            ban_until = '9999-12-31 23:59:59'
        else:
            duration = int(ban_duration)
            if ban_unit == 'hours':
                ban_until = (datetime.now() + timedelta(hours=duration))
            elif ban_unit == 'days':
                ban_until = (datetime.now() + timedelta(days=duration))
            elif ban_unit == 'months':
                ban_until = (datetime.now() + timedelta(days=duration*30))
            elif ban_unit == 'years':
                ban_until = (datetime.now() + timedelta(days=duration*365))
        
        cur.execute("""
            UPDATE client 
            SET is_banned = true, date_banned = %s 
            WHERE userid = %s
        """, (ban_until, client_id))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Client banned successfully'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cur.close()
        conn.close()

@app.route('/BeeKeeper/ban_business', methods=['POST'])
def ban_business():
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    business_id = request.json.get('business_id')
    ban_duration = request.json.get('ban_duration')
    ban_unit = request.json.get('ban_unit')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        if ban_duration == 'permanent':
            ban_until = '9999-12-31 23:59:59'
        else:
            duration = int(ban_duration)
            if ban_unit == 'hours':
                ban_until = (datetime.now() + timedelta(hours=duration))
            elif ban_unit == 'days':
                ban_until = (datetime.now() + timedelta(days=duration))
            elif ban_unit == 'months':
                ban_until = (datetime.now() + timedelta(days=duration*30))
            elif ban_unit == 'years':
                ban_until = (datetime.now() + timedelta(days=duration*365))
        
        cur.execute("""
            UPDATE business 
            SET is_banned = true, date_banned = %s 
            WHERE userid = %s
        """, (ban_until, business_id))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Business banned successfully'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cur.close()
        conn.close()
@app.route('/BeeKeeper/dismiss_report', methods=['POST'])
def dismiss_report():
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    report_id = request.json.get('report_id')
    report_type = request.json.get('report_type')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        if report_type == 'review':
            cur.execute("DELETE FROM reported_reviews WHERE reportid = %s", (report_id,))
        elif report_type == 'client':
            cur.execute("DELETE FROM reported_clients WHERE report2id = %s", (report_id,))
        elif report_type == 'business':
            cur.execute("DELETE FROM reported_business WHERE report3id = %s", (report_id,))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Report dismissed successfully'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cur.close()
        conn.close()

@app.route('/BeeKeeper/delete_review', methods=['POST'])
def delete_review():
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    review_id = request.json.get('review_id')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("DELETE FROM review WHERE reviewid = %s", (review_id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'Review deleted successfully'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cur.close()
        conn.close()

@app.route('/BeeKeeper/update_sponsored_limit', methods=['POST'])
def update_sponsored_limit():
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    subscription_id = request.json.get('subscription_id')
    new_limit = request.json.get('new_limit')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE subscription 
            SET sponsored_products_limit = %s 
            WHERE subscriptionid = %s
        """, (new_limit, subscription_id))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Sponsored limit updated successfully'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cur.close()
        conn.close()

@app.route('/BeeKeeper/Adminlogout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))




@app.route('/BeeKeeper/unban')
def unban_page():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get banned clients
        cur.execute("""
            SELECT userid, name, email, is_banned, 
                   CASE 
                       WHEN date_banned = '9999-12-31' THEN '9999-12-31'
                       ELSE date_banned
                   END as ban_until
            FROM client 
            WHERE is_banned = true
            ORDER BY name
        """)
        banned_clients = cur.fetchall()
        
        # Get banned businesses
        cur.execute("""
            SELECT userid, businessname, email, is_banned,
                   CASE 
                       WHEN date_banned = '9999-12-31' THEN '9999-12-31'
                       ELSE date_banned
                   END as ban_until
            FROM business 
            WHERE is_banned = true
            ORDER BY businessname
        """)
        banned_businesses = cur.fetchall()
        
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        return render_template('beekeeper/admin/unban.html', 
                             banned_clients=banned_clients, 
                             banned_businesses=banned_businesses,
                             current_date=datetime.now().strftime('%Y-%m-%d'),
                             admin_name=session['admin_name'])
    finally:
        cur.close()
        conn.close()

@app.route('/BeeKeeper/unban_user', methods=['POST'])
def unban_user():
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    user_id = request.json.get('user_id')
    user_type = request.json.get('user_type')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        if user_type == 'client':
            cur.execute("""
                UPDATE client 
                SET is_banned = false, date_banned = NULL 
                WHERE userid = %s
            """, (user_id,))
        elif user_type == 'business':
            cur.execute("""
                UPDATE business 
                SET is_banned = false, date_banned = NULL 
                WHERE userid = %s
            """, (user_id,))
        else:
            return jsonify({'success': False, 'message': 'Invalid user type'})
        
        conn.commit()
        return jsonify({'success': True, 'message': f'{user_type.title()} unbanned successfully'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cur.close()
        conn.close()



@app.route('/HoneyBeeHaven/create-subscription-checkout', methods=['POST'])
def create_subscription_checkout():
    """Create subscription checkout session"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))
    
    try:
        business_id = session['user_id']
        
        # Check if user has active subscription
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM subscription 
            WHERE businessid = %s AND expired = FALSE
        """, (business_id,))
        
        active_subscription = cursor.fetchone()
        
        if active_subscription:
            cursor.close()
            conn.close()
            return render_template('error.html', 
                error_message='You already have an active subscription. Please wait for it to expire before purchasing a new one.')
        
        plan_type = int(request.form.get('plan_type'))
        plan_name = request.form.get('plan_name')
        price = float(request.form.get('price'))
        products_limit = int(request.form.get('products_limit'))
        duration_days = int(request.form.get('duration_days'))
        
        cursor.close()
        conn.close()
        
        return render_template('honeybeehaven/business/subscriptioncheckout.html',
            plan_type=plan_type,
            plan_name=plan_name,
            price=price,
            products_limit=products_limit,
            duration_days=duration_days,
            user_email=session['user_email'],
            stripe_public_key=app.config['STRIPE_PUBLISHABLE_KEY']
        )
        
    except Exception as e:
        print(f"Checkout error: {e}")
        return render_template('error.html', error_message='An error occurred during checkout')

@app.route('/HoneyBeeHaven/process-subscription-payment', methods=['POST'])
def process_subscription_payment():
    """Process subscription payment"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        business_id = session['user_id']
        
        # Create charge with Stripe
        charge = stripe.Charge.create(
            amount=int(data['price'] * 100),  # Amount in paisa
            currency='inr',
            source=data['token'],
            description=f"Subscription: {data['plan_name']}"
        )
        
        if charge['status'] == 'succeeded':
            # Create subscription record
            conn = get_db_connection()
            cursor = conn.cursor()
            
            start_date = datetime.now().strftime('%Y-%m-%d')
            end_date = (datetime.now() + timedelta(days=data['duration_days'])).strftime('%Y-%m-%d')
            
            cursor.execute("""
                INSERT INTO subscription (businessid, startdate, enddate, expired, subtype, sponsored_products_limit, sponsored_products_used)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING subscriptionid
            """, (business_id, start_date, end_date, False, data['plan_type'], data['products_limit'], 0))
            
            subscription_id = cursor.fetchone()[0]
            
            # Store payment information
            cursor.execute("""
                INSERT INTO subscription_payments 
                (subscription_id, business_id, stripe_payment_intent_id, amount, payment_status, plan_name, plan_type, duration_days)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (subscription_id, business_id, charge['id'], data['price'], 'completed', data['plan_name'], data['plan_type'], data['duration_days']))
            
            # Add notification
            cursor.execute("""
                INSERT INTO notifications (user_id, notification_message, time)
                VALUES (%s, %s, %s)
            """, (business_id, f"Your {data['plan_name']} subscription has been activated successfully!", datetime.now()))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'subscription_id': subscription_id})
        else:
            return jsonify({'success': False, 'error': 'Payment failed'})
            
    except Exception as e:
        print(f"Payment processing error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/HoneyBeeHaven/my-subscriptions')
def my_subscriptions():
    """Display user's subscriptions"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))
    
    try:
        business_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT * FROM subscription 
            WHERE businessid = %s 
            ORDER BY startdate DESC
        """, (business_id,))
        
        subscriptions = cursor.fetchall()
        
        # Check and update expired subscriptions
        current_date = datetime.now().strftime('%Y-%m-%d')
        for subscription in subscriptions:
            if subscription['enddate'] < current_date and not subscription['expired']:
                cursor.execute("""
                    UPDATE subscription SET expired = TRUE WHERE subscriptionid = %s
                """, (subscription['subscriptionid'],))
                subscription['expired'] = True
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return render_template('honeybeehaven/business/my_subscriptions.html', subscriptions=subscriptions)
        
    except Exception as e:
        print(f"Subscriptions page error: {e}")
        return render_template('error.html', error_message='Error loading subscriptions')


@app.route('/HoneyBeeHaven/promote')
def promote():
    """Route to serve the promote page with subscription plans"""
    return render_template('honeybeehaven/business/promote.html')

def insert_notification(user_id, message):
    """Helper function to insert a notification"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO notifications (user_id, notification_message, time)
        VALUES (%s, %s, %s)
    """, (user_id, message, datetime.now()))
    conn.commit()
    cursor.close()
    conn.close()



# Product Sponsorship API Routes

@app.route('/HoneyBeeHaven/api/available-products/<int:subscription_id>')
def get_available_products(subscription_id):
    """Get products available for sponsorship"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        business_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get all products that are not currently sponsored
        products = []
        
        # Chemical products
        cursor.execute("""
            SELECT itemid, itemname, item_price, 'chemical' as itemtype
            FROM chemical 
            WHERE businessid = %s AND isdeleted = 0 AND issponsored = FALSE
        """, (business_id,))
        products.extend(cursor.fetchall())
        
        # Machinery products
        cursor.execute("""
            SELECT itemid, itemname, item_price, 'machinery' as itemtype
            FROM machinery 
            WHERE businessid = %s AND isdeleted = 0 AND issponsored = FALSE
        """, (business_id,))
        products.extend(cursor.fetchall())
        
        # Service products
        cursor.execute("""
            SELECT itemid, itemname, item_price, 'service' as itemtype
            FROM service 
            WHERE businessid = %s AND isdeleted = 0 AND issponsored = FALSE
        """, (business_id,))
        products.extend(cursor.fetchall())
        
        cursor.close()
        conn.close()
        
        return jsonify({'products': products})
        
    except Exception as e:
        print(f"Available products error: {e}")
        return jsonify({'error': 'Failed to load products'}), 500

@app.route('/HoneyBeeHaven/api/sponsored-products/<int:subscription_id>')
def get_sponsored_products(subscription_id):
    """Get currently sponsored products"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        business_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        products = []
        
        # Chemical products
        cursor.execute("""
            SELECT itemid, itemname, item_price, 'chemical' as itemtype
            FROM chemical 
            WHERE businessid = %s AND isdeleted = 0 AND issponsored = TRUE
        """, (business_id,))
        products.extend(cursor.fetchall())
        
        # Machinery products
        cursor.execute("""
            SELECT itemid, itemname, item_price, 'machinery' as itemtype
            FROM machinery 
            WHERE businessid = %s AND isdeleted = 0 AND issponsored = TRUE
        """, (business_id,))
        products.extend(cursor.fetchall())
        
        # Service products
        cursor.execute("""
            SELECT itemid, itemname, item_price, 'service' as itemtype
            FROM service 
            WHERE businessid = %s AND isdeleted = 0 AND issponsored = TRUE
        """, (business_id,))
        products.extend(cursor.fetchall())
        
        cursor.close()
        conn.close()
        
        return jsonify({'products': products})
        
    except Exception as e:
        print(f"Sponsored products error: {e}")
        return jsonify({'error': 'Failed to load sponsored products'}), 500

@app.route('/HoneyBeeHaven/api/sponsor-product', methods=['POST'])
def sponsor_product():
    """Sponsor a product"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        business_id = session['user_id']
        subscription_id = data['subscription_id']
        item_id = data['item_id']
        item_type = data['item_type']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check subscription limits
        cursor.execute("""
            SELECT sponsored_products_used, sponsored_products_limit, expired
            FROM subscription 
            WHERE subscriptionid = %s AND businessid = %s
        """, (subscription_id, business_id))
        
        subscription = cursor.fetchone()
        
        if not subscription:
            return jsonify({'error': 'Subscription not found'}), 404
        
        if subscription[2]:  # expired
            return jsonify({'error': 'Subscription has expired'}), 400
        
        if subscription[0] >= subscription[1]:  # used >= limit
            return jsonify({'error': 'Sponsorship limit reached'}), 400
        
        # Update product sponsorship status
        table_name = item_type
        cursor.execute(f"""
            UPDATE {table_name} 
            SET issponsored = TRUE 
            WHERE itemid = %s AND businessid = %s
        """, (item_id, business_id))
        
        # Update subscription usage
        cursor.execute("""
            UPDATE subscription 
            SET sponsored_products_used = sponsored_products_used + 1
            WHERE subscriptionid = %s
        """, (subscription_id,))
        
        # Add notification
        cursor.execute("""
            INSERT INTO notifications (user_id, notification_message, time)
            VALUES (%s, %s, %s)
        """, (business_id, f"Product has been successfully sponsored!", datetime.now()))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Sponsor product error: {e}")
        return jsonify({'error': 'Failed to sponsor product'}), 500

@app.route('/HoneyBeeHaven/api/unsponsor-product', methods=['POST'])
def unsponsor_product():
    """Remove product sponsorship"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        business_id = session['user_id']
        subscription_id = data['subscription_id']
        item_id = data['item_id']
        item_type = data['item_type']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update product sponsorship status
        table_name = item_type
        cursor.execute(f"""
            UPDATE {table_name} 
            SET issponsored = FALSE 
            WHERE itemid = %s AND businessid = %s
        """, (item_id, business_id))
        
        # Update subscription usage
        cursor.execute("""
            UPDATE subscription 
            SET sponsored_products_used = sponsored_products_used - 1
            WHERE subscriptionid = %s AND sponsored_products_used > 0
        """, (subscription_id,))
        
        # Add notification
        cursor.execute("""
            INSERT INTO notifications (user_id, notification_message, time)
            VALUES (%s, %s, %s)
        """, (business_id, f"Product sponsorship has been removed.", datetime.now()))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Unsponsor product error: {e}")
        return jsonify({'error': 'Failed to remove sponsorship'}), 500

# Notification API Routes

@app.route('/HoneyBeeHaven/api/notifications')
def get_notifications():
    """Get user notifications"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        user_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT * FROM notifications 
            WHERE user_id = %s 
            ORDER BY time DESC 
            LIMIT 50
        """, (user_id,))
        
        notifications = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({'notifications': notifications})
        
    except Exception as e:
        print(f"Get notifications error: {e}")
        return jsonify({'error': 'Failed to load notifications'}), 500

@app.route('/notifications')
def notifications():
    """Get user notifications"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
        
    cursor.execute("""
            SELECT * FROM notifications 
            WHERE user_id = %s 
            ORDER BY time DESC 
            LIMIT 50
        """, (user_id,))
        
    notifications_data = cursor.fetchall()
    cursor.close()
    conn.close()
    print(notifications_data)
    return render_template('honeybeehaven/shared/notifications.html', 
                         notifications=list(notifications_data))



@app.route('/HoneyBeeHaven/api/notifications/count')
def get_notification_count():
    """Get unread notification count"""
    if 'user_id' not in session:
        return jsonify({'count': 0})
    
    try:
        user_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM notifications 
            WHERE user_id = %s
        """, (user_id,))
        
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return jsonify({'count': count})
        
    except Exception as e:
        print(f"Get notification count error: {e}")
        return jsonify({'count': 0})

@app.route('/HoneyBeeHaven/api/notifications/mark-all-read', methods=['POST'])
def mark_all_notifications_read():
    """Mark all notifications as read (for future implementation)"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    return jsonify({'success': True})

@app.route('/HoneyBeeHaven/api/notifications/delete-all', methods=['POST'])
def delete_all_notifications():
    """Delete all notifications"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        user_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM notifications WHERE user_id = %s
        """, (user_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Delete all notifications error: {e}")
        return jsonify({'error': 'Failed to delete notifications'}), 500

@app.route('/HoneyBeeHaven/api/notifications/<int:notification_id>', methods=['DELETE'])
def delete_notification(notification_id):
    """Delete a specific notification"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        user_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM notifications 
            WHERE notification_id = %s AND user_id = %s
        """, (notification_id, user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Delete notification error: {e}")
        return jsonify({'error': 'Failed to delete notification'}), 500

# Finance Report Routes

@app.route('/HoneyBeeHaven/finance-reports')
def finance_reports():
    """Display finance reports page"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))
    
    try:
        business_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get statistics
        cursor.execute("""
            SELECT 
                COALESCE(SUM(order_cost - honeybeehavencommision), 0) as total_revenue,
                COUNT(*) as total_orders,
                COUNT(CASE WHEN order_status = 'pending' THEN 1 END) as pending_orders
            FROM order_table ot
            JOIN cart c ON ot.cartid = c.cartid
            JOIN cart_items ci ON c.cartid = ci.cartid
            WHERE ci.businessid = %s
        """, (business_id,))
        
        stats = cursor.fetchone()
        
        # Get this month revenue
        cursor.execute("""
            SELECT COALESCE(SUM(order_cost - honeybeehavencommision), 0)
            FROM order_table ot
            JOIN cart c ON ot.cartid = c.cartid
            JOIN cart_items ci ON c.cartid = ci.cartid
            WHERE ci.businessid = %s 
            AND EXTRACT(MONTH FROM ot.orderdate) = EXTRACT(MONTH FROM CURRENT_DATE)
            AND EXTRACT(YEAR FROM ot.orderdate) = EXTRACT(YEAR FROM CURRENT_DATE)
        """, (business_id,))
        
        this_month_revenue = cursor.fetchone()[0]
        
        # Get revenue by category
        revenue_breakdown = {}
        
        for table in ['chemical', 'machinery', 'service']:
            cursor.execute(f"""
                SELECT COALESCE(SUM(ci.total_price), 0)
                FROM cart_items ci
                JOIN order_table ot ON ci.cartid = ot.cartid
                WHERE ci.businessid = %s AND ci.itemtype = %s
            """, (business_id, table))
            revenue_breakdown[f"{table}_revenue"] = cursor.fetchone()[0]
        
        # Get monthly revenue data for chart
        cursor.execute("""
            SELECT 
                TO_CHAR(ot.orderdate, 'Month') as month,
                COALESCE(SUM(order_cost - honeybeehavencommision), 0) as revenue
            FROM order_table ot
            JOIN cart c ON ot.cartid = c.cartid
            JOIN cart_items ci ON c.cartid = ci.cartid
            WHERE ci.businessid = %s 
            AND ot.orderdate >= CURRENT_DATE - INTERVAL '12 months'
            GROUP BY EXTRACT(MONTH FROM ot.orderdate), TO_CHAR(ot.orderdate, 'Month')
            ORDER BY EXTRACT(MONTH FROM ot.orderdate)
        """, (business_id,))
        
        monthly_data = cursor.fetchall()
        monthly_labels = [row[0].strip() for row in monthly_data]
        monthly_revenue = [float(row[1]) for row in monthly_data]
        
        # Get order status data for chart
        cursor.execute("""
            SELECT 
                order_status,
                COUNT(*) as count
            FROM order_table ot
            JOIN cart c ON ot.cartid = c.cartid
            JOIN cart_items ci ON c.cartid = ci.cartid
            WHERE ci.businessid = %s
            GROUP BY order_status
        """, (business_id,))
        
        status_data = cursor.fetchall()
        order_status_data = [0, 0, 0, 0]  # [completed, pending, processing, cancelled]
        
        for status, count in status_data:
            if status.lower() == 'completed':
                order_status_data[0] = count
            elif status.lower() == 'pending':
                order_status_data[1] = count
            elif status.lower() == 'processing':
                order_status_data[2] = count
            elif status.lower() == 'cancelled':
                order_status_data[3] = count
        
        cursor.close()
        conn.close()
        
        return render_template('honeybeehaven/business/finance_reports.html',
            total_revenue=stats[0],
            total_orders=stats[1],
            pending_orders=stats[2],
            this_month_revenue=this_month_revenue,
            current_date=datetime.now().strftime('%Y-%m-%d'),
            monthly_labels=monthly_labels,
            monthly_revenue=monthly_revenue,
            order_status_data=order_status_data,
            **revenue_breakdown
        )
        
    except Exception as e:
        print(f"Finance reports error: {e}")
        return render_template('error.html', error_message='Error loading finance reports')

@app.route('/HoneyBeeHaven/api/finance-report-data')
def get_finance_report_data():
    """Get finance report data for table"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        business_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT 
                ot.orderid,
                ot.orderdate,
                cl.name as customer_name,
                COUNT(ci.cart_item_id) as items_count,
                ot.order_cost,
                ot.honeybeehavencommision,
                ot.order_status
            FROM order_table ot
            JOIN cart c ON ot.cartid = c.cartid
            JOIN cart_items ci ON c.cartid = ci.cartid
            JOIN client cl ON ot.clientid = cl.userid
            WHERE ci.businessid = %s
            GROUP BY ot.orderid, ot.orderdate, cl.name, ot.order_cost, ot.honeybeehavencommision, ot.order_status
            ORDER BY ot.orderdate DESC
            LIMIT 100
        """, (business_id,))
        
        orders = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({'orders': orders})
        
    except Exception as e:
        print(f"Finance report data error: {e}")
        return jsonify({'error': 'Failed to load report data'}), 500

@app.route('/HoneyBeeHaven/export-finance-report')
def export_finance_report():
    """Export finance report to Excel"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))
    
    try:
        business_id = session['user_id']
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        report_type = request.args.get('report_type', 'revenue')
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Base query
        base_query = """
            SELECT 
                ot.orderid as "Order ID",
                ot.orderdate as "Date",
                cl.name as "Customer Name",
                cl.email as "Customer Email",
                COUNT(ci.cart_item_id) as "Items Count",
                ot.order_cost as "Order Value",
                ot.honeybeehavencommision as "Platform Commission",
                (ot.order_cost - ot.honeybeehavencommision) as "Net Revenue",
                ot.order_status as "Order Status",
                ot.payment_status as "Payment Status"
            FROM order_table ot
            JOIN cart c ON ot.cartid = c.cartid
            JOIN cart_items ci ON c.cartid = ci.cartid
            JOIN client cl ON ot.clientid = cl.userid
            WHERE ci.businessid = %s
        """
        
        params = [business_id]
        
        if start_date:
            base_query += " AND ot.orderdate >= %s"
            params.append(start_date)
        
        if end_date:
            base_query += " AND ot.orderdate <= %s"
            params.append(end_date)
        
        base_query += """
            GROUP BY ot.orderid, ot.orderdate, cl.name, cl.email, ot.order_cost, ot.honeybeehavencommision, ot.order_status, ot.payment_status
            ORDER BY ot.orderdate DESC
        """
        
        cursor.execute(base_query, params)
        data = cursor.fetchall()
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Main report sheet
            df.to_excel(writer, sheet_name='Financial Report', index=False)
            
            # Summary sheet
            summary_data = {
                'Metric': ['Total Orders', 'Total Revenue', 'Total Commission', 'Net Revenue', 'Average Order Value'],
                'Value': [
                    len(df),
                    df['Order Value'].sum() if not df.empty else 0,
                    df['Platform Commission'].sum() if not df.empty else 0,
                    df['Net Revenue'].sum() if not df.empty else 0,
                    df['Order Value'].mean() if not df.empty else 0
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        output.seek(0)
        
        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename=finance_report_{datetime.now().strftime("%Y%m%d")}.xlsx'
        
        cursor.close()
        conn.close()
        
        return response
        
    except Exception as e:
        print(f"Export error: {e}")
        return render_template('error.html', error_message='Error exporting report')

@app.route('/HoneyBeeHaven/subscription-success')
def subscription_success():
    """Subscription success page"""
    subscription_id = request.args.get('subscription_id')
    return render_template('honeybeehaven/business/subscription_success.html', subscription_id=subscription_id)


@app.route('/HoneyBeeHaven/api/finance-dashboard-data')
def get_finance_dashboard_data():
    """Get comprehensive dashboard data for finance reports"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        business_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get comprehensive statistics
        cursor.execute("""
            SELECT 
                COALESCE(SUM(order_cost - honeybeehavencommision), 0) as total_revenue,
                COUNT(*) as total_orders,
                COUNT(CASE WHEN order_status = 'pending' THEN 1 END) as pending_orders,
                AVG(order_cost) as avg_order_value
            FROM order_table ot
            JOIN cart c ON ot.cartid = c.cartid
            JOIN cart_items ci ON c.cartid = ci.cartid
            WHERE ci.businessid = %s
        """, (business_id,))
        
        stats = cursor.fetchone()
        
        # Get this month and last month revenue for comparison
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE 
                    WHEN EXTRACT(MONTH FROM ot.orderdate) = EXTRACT(MONTH FROM CURRENT_DATE)
                    AND EXTRACT(YEAR FROM ot.orderdate) = EXTRACT(YEAR FROM CURRENT_DATE)
                    THEN order_cost - honeybeehavencommision 
                END), 0) as this_month_revenue,
                COALESCE(SUM(CASE 
                    WHEN EXTRACT(MONTH FROM ot.orderdate) = EXTRACT(MONTH FROM CURRENT_DATE - INTERVAL '1 month')
                    AND EXTRACT(YEAR FROM ot.orderdate) = EXTRACT(YEAR FROM CURRENT_DATE - INTERVAL '1 month')
                    THEN order_cost - honeybeehavencommision 
                END), 0) as last_month_revenue
            FROM order_table ot
            JOIN cart c ON ot.cartid = c.cartid
            JOIN cart_items ci ON c.cartid = ci.cartid
            WHERE ci.businessid = %s
        """, (business_id,))
        
        monthly_comparison = cursor.fetchone()
        
        # Get revenue by category
        revenue_breakdown = {}
        for table in ['chemical', 'machinery', 'service']:
            cursor.execute(f"""
                SELECT COALESCE(SUM(ci.total_price), 0)
                FROM cart_items ci
                JOIN order_table ot ON ci.cartid = ot.cartid
                WHERE ci.businessid = %s AND ci.itemtype = %s
            """, (business_id, table))
            revenue_breakdown[f"{table}_revenue"] = float(cursor.fetchone()[0])
        
        # Get monthly revenue data for chart (last 12 months)
        cursor.execute("""
            SELECT 
                TO_CHAR(ot.orderdate, 'Mon YYYY') as month_year,
                EXTRACT(MONTH FROM ot.orderdate) as month_num,
                COALESCE(SUM(order_cost - honeybeehavencommision), 0) as revenue
            FROM order_table ot
            JOIN cart c ON ot.cartid = c.cartid
            JOIN cart_items ci ON c.cartid = ci.cartid
            WHERE ci.businessid = %s 
            AND ot.orderdate >= CURRENT_DATE - INTERVAL '12 months'
            GROUP BY EXTRACT(MONTH FROM ot.orderdate), EXTRACT(YEAR FROM ot.orderdate), TO_CHAR(ot.orderdate, 'Mon YYYY')
            ORDER BY EXTRACT(YEAR FROM ot.orderdate), EXTRACT(MONTH FROM ot.orderdate)
        """, (business_id,))
        
        monthly_data = cursor.fetchall()
        monthly_labels = [row[0] for row in monthly_data]
        monthly_revenue = [float(row[2]) for row in monthly_data]
        
        # Get order status distribution
        cursor.execute("""
            SELECT 
                LOWER(order_status) as status,
                COUNT(*) as count
            FROM order_table ot
            JOIN cart c ON ot.cartid = c.cartid
            JOIN cart_items ci ON c.cartid = ci.cartid
            WHERE ci.businessid = %s
            GROUP BY LOWER(order_status)
        """, (business_id,))
        
        status_data = cursor.fetchall()
        order_status_data = [0, 0, 0, 0]  # [completed, pending, processing, cancelled]
        
        status_mapping = {
            'completed': 0, 'delivered': 0,
            'pending': 1,
            'processing': 2, 'shipped': 2,
            'cancelled': 3, 'refunded': 3
        }
        
        for status, count in status_data:
            index = status_mapping.get(status, 1)  # Default to pending
            order_status_data[index] += count
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'total_revenue': float(stats[0]),
            'total_orders': stats[1],
            'pending_orders': stats[2],
            'avg_order_value': float(stats[3]) if stats[3] else 0,
            'this_month_revenue': float(monthly_comparison[0]),
            'last_month_revenue': float(monthly_comparison[1]),
            'monthly_labels': monthly_labels,
            'monthly_revenue': monthly_revenue,
            'order_status_data': order_status_data,
            **revenue_breakdown
        })
        
    except Exception as e:
        print(f"Finance dashboard data error: {e}")
        return jsonify({'error': 'Failed to load dashboard data'}), 500

@app.route('/HoneyBeeHaven/api/generate-custom-report')
def generate_custom_report():
    """Generate custom financial report based on filters"""
    if 'user_id' not in session or session.get('user_type') != 'business':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        business_id = session['user_id']
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        report_type = request.args.get('report_type', 'revenue')
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        base_query = """
            SELECT 
                ot.orderid as id,
                ot.orderdate::date as date,
                CONCAT('Order #', ot.orderid, ' - ', cl.name) as description,
                ci.itemtype as category,
                ot.order_cost as amount,
                ot.honeybeehavencommision as commission,
                (ot.order_cost - ot.honeybeehavencommision) as net,
                ot.order_status as status
            FROM order_table ot
            JOIN cart c ON ot.cartid = c.cartid
            JOIN cart_items ci ON c.cartid = ci.cartid
            JOIN client cl ON ot.clientid = cl.userid
            WHERE ci.businessid = %s
        """
        
        params = [business_id]
        
        if start_date:
            base_query += " AND ot.orderdate >= %s"
            params.append(start_date)
        
        if end_date:
            base_query += " AND ot.orderdate <= %s"
            params.append(end_date)
        
        if report_type == 'orders':
            base_query += " AND ot.order_status IN ('completed', 'delivered')"
        elif report_type == 'commission':
            base_query += " AND ot.honeybeehavencommision > 0"
        
        base_query += " GROUP BY ot.orderid, ot.orderdate, cl.name, ci.itemtype, ot.order_cost, ot.honeybeehavencommision, ot.order_status ORDER BY ot.orderdate DESC LIMIT 50"
        
        cursor.execute(base_query, params)
        report_data = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({'report': report_data})
        
    except Exception as e:
        print(f"Custom report generation error: {e}")
        return jsonify({'error': 'Failed to generate custom report'}), 500


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8000))
    app.run(host="0.0.0.0", port=port)