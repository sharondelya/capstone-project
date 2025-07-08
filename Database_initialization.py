import psycopg2
import logging

# Database configuration
DB_CONFIG = {
    'host': 'pg-14c2d863-ijazabdullah127-f508.c.aivencloud.com',
    'port': 11068,
    'database': 'defaultdb',
    'user': 'avnadmin',
    'password': 'AVNS_Tjku63uorJ5CV1cKt_2',
    'sslmode': 'require'
}

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    """Initialize database with tables and sequences"""
    try:
        # Connect to database
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        logger.info("✅ Connected to database successfully")
        
        # Execute the complete SQL script
        sql_script = '''
        BEGIN;

        -- Create all tables with IF NOT EXISTS
        CREATE TABLE IF NOT EXISTS public.admin2
        (
            adminid serial NOT NULL,
            admin_email character varying(255),
            admin_name character varying(255),
            admin_password character varying(255),
            CONSTRAINT admin2_pkey PRIMARY KEY (adminid)
        );

        CREATE TABLE IF NOT EXISTS public.business
        (
            userid serial NOT NULL,
            address character varying(255),
            date_banned timestamp without time zone,
            datejoined character varying(255),
            email character varying(255) NOT NULL,
            image bytea,
            is_banned boolean DEFAULT false,
            name character varying(255) NOT NULL,
            password character varying(255) NOT NULL,
            primarylocation character varying(255),
            bankaccountnumber character varying(255),
            businessdescription text,
            businessname character varying(255),
            businessrating real NOT NULL DEFAULT 0.0,
            contactinfo character varying(255),
            targetkeywords text,
            CONSTRAINT business_pkey PRIMARY KEY (userid),
            CONSTRAINT business_email_key UNIQUE (email)
        );

        CREATE TABLE IF NOT EXISTS public.client
        (
            userid serial NOT NULL,
            address character varying(255),
            date_banned timestamp without time zone,
            datejoined character varying(255),
            email character varying(255) NOT NULL,
            image bytea,
            is_banned boolean DEFAULT false,
            name character varying(255) NOT NULL,
            password character varying(255) NOT NULL,
            primarylocation character varying(255),
            age character varying(255),
            gender character varying(255),
            CONSTRAINT client_pkey PRIMARY KEY (userid),
            CONSTRAINT client_email_key UNIQUE (email)
        );

        CREATE TABLE IF NOT EXISTS public.cart
        (
            cartid serial NOT NULL,
            userid integer NOT NULL,
            created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
            is_active boolean DEFAULT true,
            CONSTRAINT cart_pkey PRIMARY KEY (cartid)
        );

        CREATE TABLE IF NOT EXISTS public.cart_items
        (
            cart_item_id serial NOT NULL,
            cartid integer NOT NULL,
            itemid integer NOT NULL,
            itemtype character varying(50) NOT NULL,
            quantity integer NOT NULL,
            unit_price numeric(10, 2) NOT NULL,
            total_price numeric(10, 2) NOT NULL,
            businessid integer NOT NULL,
            added_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT cart_items_pkey PRIMARY KEY (cart_item_id)
        );

        CREATE TABLE IF NOT EXISTS public.chemical
        (
            itemid serial NOT NULL,
            itemname character varying(255) NOT NULL,
            item_price numeric(10, 2) NOT NULL,
            itemdescription text,
            chemical_type character varying(255) NOT NULL,
            metricsystem character varying(255) NOT NULL,
            expirydate date NOT NULL,
            quantity numeric(10, 2) NOT NULL,
            hazardlevel numeric(5, 2) NOT NULL,
            quantityinstock integer NOT NULL,
            image bytea,
            businessid integer NOT NULL,
            itemrating numeric(3, 2) DEFAULT 0.0,
            date_created timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
            isdeleted integer DEFAULT 0,
            issponsored boolean DEFAULT false,
            CONSTRAINT chemical_pkey PRIMARY KEY (itemid)
        );

        CREATE TABLE IF NOT EXISTS public.machinery
        (
            itemid serial NOT NULL,
            itemname character varying(255) NOT NULL,
            item_price numeric(10, 2) NOT NULL,
            itemdescription text,
            machinetype character varying(255) NOT NULL,
            machinedimension character varying(255) NOT NULL,
            machineweight numeric(10, 2) NOT NULL,
            powersource character varying(255) NOT NULL,
            warranty integer NOT NULL,
            quantityinstock integer NOT NULL,
            image bytea,
            businessid integer NOT NULL,
            itemrating numeric(3, 2) DEFAULT 0.0,
            date_created timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
            isdeleted integer DEFAULT 0,
            issponsored boolean DEFAULT false,
            CONSTRAINT machinery_pkey PRIMARY KEY (itemid)
        );

        CREATE TABLE IF NOT EXISTS public.service
        (
            itemid serial NOT NULL,
            itemname character varying(255) NOT NULL,
            item_price numeric(10, 2) NOT NULL,
            itemdescription text,
            servicetype character varying(255) NOT NULL,
            isavailable boolean NOT NULL DEFAULT true,
            basecharges numeric(10, 2) NOT NULL,
            image bytea,
            businessid integer NOT NULL,
            itemrating numeric(3, 2) DEFAULT 0.0,
            date_created timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
            isdeleted integer DEFAULT 0,
            issponsored boolean DEFAULT false,
            CONSTRAINT service_pkey PRIMARY KEY (itemid)
        );

        CREATE TABLE IF NOT EXISTS public.conversation
        (
            conversationid serial NOT NULL,
            businessid integer,
            clientid integer,
            CONSTRAINT conversation_pkey PRIMARY KEY (conversationid)
        );

        CREATE TABLE IF NOT EXISTS public.message
        (
            messageid serial NOT NULL,
            conversationid integer,
            receiverid integer,
            senderid integer,
            text character varying(255),
            "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT message_pkey PRIMARY KEY (messageid)
        );

        CREATE TABLE IF NOT EXISTS public.notifications
        (
            notification_id serial NOT NULL,
            notification_message character varying(255),
            "time" timestamp without time zone,
            user_id integer,
            CONSTRAINT notifications_pkey PRIMARY KEY (notification_id)
        );

        CREATE TABLE IF NOT EXISTS public.order_table
        (
            orderid serial NOT NULL,
            clientid integer NOT NULL,
            cartid integer NOT NULL,
            order_cost numeric(10, 2) NOT NULL,
            honeybeehavencommision numeric(10, 2) NOT NULL,
            totalcost numeric(10, 2) NOT NULL,
            orderdate timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
            shippingaddress text,
            order_status character varying(50) DEFAULT 'pending'::character varying,
            payment_status character varying(50) DEFAULT 'pending'::character varying,
            stripe_payment_intent_id character varying(255),
            CONSTRAINT order_table_pkey PRIMARY KEY (orderid)
        );

        CREATE TABLE IF NOT EXISTS public.order_details
        (
            orderdetailkey serial NOT NULL,
            item_delivery_date character varying(255),
            item_dispatch_date character varying(255),
            itemid integer,
            itemqty integer,
            itemtype character varying(255),
            orderid integer,
            delivery_status character varying(50) DEFAULT 'Processing'::character varying,
            CONSTRAINT order_details_pkey PRIMARY KEY (orderdetailkey)
        );

        CREATE TABLE IF NOT EXISTS public.payment
        (
            paymentid serial NOT NULL,
            orderid integer,
            subscriptionid integer,
            transactionaccount character varying(255),
            transactionamount double precision NOT NULL,
            transactiondate character varying(255),
            transactionid character varying(255),
            transactionplatform character varying(255),
            CONSTRAINT payment_pkey PRIMARY KEY (paymentid)
        );

        CREATE TABLE IF NOT EXISTS public.review
        (
            reviewid serial NOT NULL,
            clientid integer,
            date text,
            itemid integer,
            rating integer,
            text text,
            title text,
            producttype character varying(50),
            orderid integer,
            CONSTRAINT review_pkey PRIMARY KEY (reviewid),
            CONSTRAINT unique_review_per_order_item UNIQUE (clientid, orderid, itemid, producttype)
        );

        CREATE TABLE IF NOT EXISTS public.subscription
        (
            subscriptionid serial NOT NULL,
            businessid integer,
            enddate character varying(255),
            expired boolean,
            startdate character varying(255),
            subtype integer,
            sponsored_products_limit integer DEFAULT 0,
            sponsored_products_used integer DEFAULT 0,
            CONSTRAINT subscription_pkey PRIMARY KEY (subscriptionid)
        );

        CREATE TABLE IF NOT EXISTS public.subscription_payments
        (
            payment_id serial NOT NULL,
            subscription_id integer NOT NULL,
            business_id integer NOT NULL,
            stripe_payment_intent_id character varying(255),
            stripe_payment_method_id character varying(255),
            amount numeric(10, 2) NOT NULL,
            currency character varying(3) DEFAULT 'INR'::character varying,
            payment_status character varying(50) DEFAULT 'pending'::character varying,
            payment_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
            plan_name character varying(100),
            plan_type integer NOT NULL,
            duration_days integer NOT NULL,
            CONSTRAINT subscription_payments_pkey PRIMARY KEY (payment_id)
        );

        CREATE TABLE IF NOT EXISTS public.reported_reviews
        (
            reportid serial NOT NULL,
            complaineeid integer,
            complainerid integer,
            report_reason character varying(255),
            report_type character varying(255),
            review_content character varying(255),
            reviewid integer,
            CONSTRAINT reported_reviews_pkey PRIMARY KEY (reportid)
        );

        CREATE TABLE IF NOT EXISTS public.reported_clients
        (
            report2id serial NOT NULL,
            complainee2id integer,
            complainer2id integer,
            report_reason2 character varying(255),
            report_type character varying(255),
            CONSTRAINT reported_clients_pkey PRIMARY KEY (report2id)
        );

        CREATE TABLE IF NOT EXISTS public.reported_business
        (
            report3id serial NOT NULL,
            complainee3id integer,
            complainer3id integer,
            report_reason3 character varying(255),
            report_type character varying(255),
            CONSTRAINT reported_business_pkey PRIMARY KEY (report3id)
        );

        CREATE TABLE IF NOT EXISTS public.service_cart
        (
            cartid serial NOT NULL,
            businessid integer,
            itemid integer,
            itemqty integer,
            itemtype character varying(255),
            price double precision NOT NULL,
            userid integer,
            CONSTRAINT service_cart_pkey PRIMARY KEY (cartid)
        );

        CREATE TABLE IF NOT EXISTS public.contact
        (
            email character varying(255) NOT NULL,
            message character varying(255),
            name character varying(255),
            subject character varying(255),
            CONSTRAINT contact_pkey PRIMARY KEY (email)
        );

        COMMIT;
        '''
        
        # Execute table creation
        cursor.execute(sql_script)
        logger.info("✅ Tables created successfully")
        
        # Set sequence starting values to avoid conflicts
        sequence_updates = '''
        -- Set sequence starting values (only if they haven't been used yet)
        DO $$
        DECLARE
            seq_exists boolean;
            seq_is_called boolean;
        BEGIN
            -- Admin sequence (1-999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'admin2_adminid_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM admin2_adminid_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('admin2_adminid_seq', 1, false);
                END IF;
            END IF;

            -- Business sequence (1000-9999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'business_userid_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM business_userid_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('business_userid_seq', 1000, false);
                END IF;
            END IF;

            -- Client sequence (10000-19999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'client_userid_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM client_userid_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('client_userid_seq', 10000, false);
                END IF;
            END IF;

            -- Cart sequence (20000-29999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'cart_cartid_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM cart_cartid_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('cart_cartid_seq', 20000, false);
                END IF;
            END IF;

            -- Cart items sequence (30000-39999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'cart_items_cart_item_id_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM cart_items_cart_item_id_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('cart_items_cart_item_id_seq', 30000, false);
                END IF;
            END IF;

            -- Chemical sequence (40000-49999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'chemical_itemid_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM chemical_itemid_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('chemical_itemid_seq', 40000, false);
                END IF;
            END IF;

            -- Machinery sequence (50000-59999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'machinery_itemid_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM machinery_itemid_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('machinery_itemid_seq', 50000, false);
                END IF;
            END IF;

            -- Service sequence (60000-69999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'service_itemid_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM service_itemid_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('service_itemid_seq', 60000, false);
                END IF;
            END IF;

            -- Continue with other sequences...
            -- Conversation sequence (70000-79999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'conversation_conversationid_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM conversation_conversationid_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('conversation_conversationid_seq', 70000, false);
                END IF;
            END IF;

            -- Message sequence (80000-89999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'message_messageid_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM message_messageid_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('message_messageid_seq', 80000, false);
                END IF;
            END IF;

            -- Notifications sequence (90000-99999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'notifications_notification_id_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM notifications_notification_id_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('notifications_notification_id_seq', 90000, false);
                END IF;
            END IF;

            -- Order table sequence (100000-199999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'order_table_orderid_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM order_table_orderid_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('order_table_orderid_seq', 100000, false);
                END IF;
            END IF;

            -- Order details sequence (200000-299999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'order_details_orderdetailkey_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM order_details_orderdetailkey_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('order_details_orderdetailkey_seq', 200000, false);
                END IF;
            END IF;

            -- Payment sequence (300000-399999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'payment_paymentid_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM payment_paymentid_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('payment_paymentid_seq', 300000, false);
                END IF;
            END IF;

            -- Review sequence (400000-499999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'review_reviewid_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM review_reviewid_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('review_reviewid_seq', 400000, false);
                END IF;
            END IF;

            -- Subscription sequence (500000-599999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'subscription_subscriptionid_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM subscription_subscriptionid_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('subscription_subscriptionid_seq', 500000, false);
                END IF;
            END IF;

            -- Subscription payments sequence (600000-699999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'subscription_payments_payment_id_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM subscription_payments_payment_id_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('subscription_payments_payment_id_seq', 600000, false);
                END IF;
            END IF;

            -- Reported reviews sequence (700000-799999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'reported_reviews_reportid_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM reported_reviews_reportid_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('reported_reviews_reportid_seq', 700000, false);
                END IF;
            END IF;

            -- Reported clients sequence (800000-899999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'reported_clients_report2id_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM reported_clients_report2id_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('reported_clients_report2id_seq', 800000, false);
                END IF;
            END IF;

            -- Reported business sequence (900000-999999)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'reported_business_report3id_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM reported_business_report3id_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('reported_business_report3id_seq', 900000, false);
                END IF;
            END IF;

            -- Service cart sequence (1000000+)
            SELECT EXISTS(SELECT 1 FROM information_schema.sequences WHERE sequence_name = 'service_cart_cartid_seq') INTO seq_exists;
            IF seq_exists THEN
                SELECT is_called FROM service_cart_cartid_seq INTO seq_is_called;
                IF NOT seq_is_called THEN
                    PERFORM setval('service_cart_cartid_seq', 1000000, false);
                END IF;
            END IF;
        END $$;
        '''
        
        cursor.execute(sequence_updates)
        logger.info("✅ Sequence ranges set successfully")
        
        # Add foreign key constraints
        fk_constraints = '''
        DO $$
        BEGIN
            -- Cart to client
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'cart_userid_fkey'
            ) THEN
                ALTER TABLE public.cart 
                ADD CONSTRAINT cart_userid_fkey 
                FOREIGN KEY (userid) REFERENCES public.client (userid) 
                ON DELETE CASCADE;
            END IF;

            -- Cart items to business
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'cart_items_businessid_fkey'
            ) THEN
                ALTER TABLE public.cart_items 
                ADD CONSTRAINT cart_items_businessid_fkey 
                FOREIGN KEY (businessid) REFERENCES public.business (userid) 
                ON DELETE CASCADE;
            END IF;

            -- Cart items to cart
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'cart_items_cartid_fkey'
            ) THEN
                ALTER TABLE public.cart_items 
                ADD CONSTRAINT cart_items_cartid_fkey 
                FOREIGN KEY (cartid) REFERENCES public.cart (cartid) 
                ON DELETE CASCADE;
            END IF;

            -- Chemical to business
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'chemical_businessid_fkey'
            ) THEN
                ALTER TABLE public.chemical 
                ADD CONSTRAINT chemical_businessid_fkey 
                FOREIGN KEY (businessid) REFERENCES public.business (userid) 
                ON DELETE CASCADE;
            END IF;

            -- Machinery to business
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'machinery_businessid_fkey'
            ) THEN
                ALTER TABLE public.machinery 
                ADD CONSTRAINT machinery_businessid_fkey 
                FOREIGN KEY (businessid) REFERENCES public.business (userid) 
                ON DELETE CASCADE;
            END IF;

            -- Service to business
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'service_businessid_fkey'
            ) THEN
                ALTER TABLE public.service 
                ADD CONSTRAINT service_businessid_fkey 
                FOREIGN KEY (businessid) REFERENCES public.business (userid) 
                ON DELETE CASCADE;
            END IF;

            -- Order table constraints
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'order_table_cartid_fkey'
            ) THEN
                ALTER TABLE public.order_table 
                ADD CONSTRAINT order_table_cartid_fkey 
                FOREIGN KEY (cartid) REFERENCES public.cart (cartid) 
                ON DELETE CASCADE;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'order_table_clientid_fkey'
            ) THEN
                ALTER TABLE public.order_table 
                ADD CONSTRAINT order_table_clientid_fkey 
                FOREIGN KEY (clientid) REFERENCES public.client (userid) 
                ON DELETE CASCADE;
            END IF;

            -- Review to order
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'fk_review_order'
            ) THEN
                ALTER TABLE public.review 
                ADD CONSTRAINT fk_review_order 
                FOREIGN KEY (orderid) REFERENCES public.order_table (orderid);
            END IF;

            -- Subscription payments constraints
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'subscription_payments_business_id_fkey'
            ) THEN
                ALTER TABLE public.subscription_payments 
                ADD CONSTRAINT subscription_payments_business_id_fkey 
                FOREIGN KEY (business_id) REFERENCES public.business (userid) 
                ON DELETE CASCADE;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'subscription_payments_subscription_id_fkey'
            ) THEN
                ALTER TABLE public.subscription_payments 
                ADD CONSTRAINT subscription_payments_subscription_id_fkey 
                FOREIGN KEY (subscription_id) REFERENCES public.subscription (subscriptionid) 
                ON DELETE CASCADE;
            END IF;
        END $$;
        '''
        
        cursor.execute(fk_constraints)
        logger.info("✅ Foreign key constraints created successfully")
        
        # Create indexes
        indexes = '''
        CREATE INDEX IF NOT EXISTS idx_chemical_businessid ON public.chemical(businessid);
        CREATE INDEX IF NOT EXISTS idx_machinery_businessid ON public.machinery(businessid);
        CREATE INDEX IF NOT EXISTS idx_service_businessid ON public.service(businessid);
        CREATE INDEX IF NOT EXISTS idx_cart_userid ON public.cart(userid);
        CREATE INDEX IF NOT EXISTS idx_cart_items_cartid ON public.cart_items(cartid);
        CREATE INDEX IF NOT EXISTS idx_order_table_clientid ON public.order_table(clientid);
        CREATE INDEX IF NOT EXISTS idx_review_orderid ON public.review(orderid);
        CREATE INDEX IF NOT EXISTS idx_admin_email ON public.admin2(admin_email);
        '''
        
        cursor.execute(indexes)
        logger.info("✅ Indexes created successfully")
        
        # Insert default admin user if it doesn't exist
        insert_admin_user(cursor)
        
        # Show table count
        cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
        table_count = cursor.fetchone()[0]
        logger.info(f"✅ Database initialized with {table_count} tables")
        
        # Show ID ranges
        logger.info("\n📋 ID Ranges for Tables:")
        logger.info("  admin2: 1-999")
        logger.info("  business: 1000-9999") 
        logger.info("  client: 10000-19999")
        logger.info("  cart: 20000-29999")
        logger.info("  cart_items: 30000-39999")
        logger.info("  chemical: 40000-49999")
        logger.info("  machinery: 50000-59999")
        logger.info("  service: 60000-69999")
        logger.info("  conversation: 70000-79999")
        logger.info("  message: 80000-89999")
        logger.info("  notifications: 90000-99999")
        logger.info("  order_table: 100000-199999")
        logger.info("  order_details: 200000-299999")
        logger.info("  payment: 300000-399999")
        logger.info("  review: 400000-499999")
        logger.info("  subscription: 500000-599999")
        logger.info("  subscription_payments: 600000-699999")
        logger.info("  reported_reviews: 700000-799999")
        logger.info("  reported_clients: 800000-899999")
        logger.info("  reported_business: 900000-999999")
        logger.info("  service_cart: 1000000+")
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialization completed successfully!")
        return True
        
    except psycopg2.Error as e:
        logger.error(f"❌ Database error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False

def insert_admin_user(cursor):
    """Insert default admin user if it doesn't exist"""
    try:
        # Check if admin user already exists
        cursor.execute("SELECT COUNT(*) FROM admin2 WHERE admin_email = %s", ('admin@honeybee',))
        admin_count = cursor.fetchone()[0]
        
        if admin_count == 0:
            # Insert default admin user
            cursor.execute(
                "INSERT INTO admin2 (admin_email, admin_name, admin_password) VALUES (%s, %s, %s)",
                ('admin@honeybee', 'Albert', 'Abc12345')
            )
            logger.info("✅ Default admin user 'Albert' created successfully")
            logger.info("   📧 Email: admin@honeybee")
            logger.info("   🔐 Password: Abc12345")
        else:
            logger.info("ℹ️  Admin user already exists, skipping creation")
            
    except psycopg2.Error as e:
        logger.error(f"❌ Error creating admin user: {e}")
        raise

# Quick connection test
def test_connection():
    """Test database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        logger.info(f"✅ Connected to: {version}")
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        return False

def verify_admin_user():
    """Verify admin user exists and show details"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("SELECT adminid, admin_email, admin_name FROM admin2 WHERE admin_email = %s", ('admin@honeybee',))
        admin = cursor.fetchone()
        
        if admin:
            logger.info(f"✅ Admin user verified:")
            logger.info(f"   ID: {admin[0]}")
            logger.info(f"   Email: {admin[1]}")
            logger.info(f"   Name: {admin[2]}")
        else:
            logger.warning("⚠️  Admin user not found!")
            
        conn.close()
        return admin is not None
        
    except Exception as e:
        logger.error(f"❌ Error verifying admin user: {e}")
        return False

if __name__ == "__main__":
    logger.info("🚀 Starting AgriSmart Database Initialization...")
    
    # Test connection first
    if test_connection():
        # Initialize database
        if init_database():
            logger.info("🎉 All done! Your database is ready to use.")
            
            # Verify admin user was created
            logger.info("\n🔍 Verifying admin user...")
            verify_admin_user()
            
            logger.info("\n📝 Default Admin Credentials:")
            logger.info("   Email: admin@honeybee")
            logger.info("   Username: Albert")
            logger.info("   Password: Abc12345")
            logger.info("\n⚠️  Remember to change the default password after first login!")
            
        else:
            logger.error("❌ Database initialization failed")
    else:
        logger.error("❌ Cannot connect to database")