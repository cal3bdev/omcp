"""Large E-Commerce API for testing modular OMCP (micro-MCPs).

This API simulates a large enterprise e-commerce platform with ~100 endpoints
spread across multiple domains to test the modular MCP splitting functionality.
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(
    title="MegaStore E-Commerce API",
    description="Large enterprise e-commerce platform API",
    version="3.0.0",
)

# ============================================================================
# In-memory databases
# ============================================================================
users_db: dict[str, dict] = {}
products_db: dict[str, dict] = {}
categories_db: dict[str, dict] = {}
orders_db: dict[str, dict] = {}
carts_db: dict[str, dict] = {}
reviews_db: dict[str, dict] = {}
wishlists_db: dict[str, dict] = {}
addresses_db: dict[str, dict] = {}
payments_db: dict[str, dict] = {}
shipments_db: dict[str, dict] = {}
coupons_db: dict[str, dict] = {}
inventory_db: dict[str, dict] = {}
notifications_db: dict[str, dict] = {}
support_tickets_db: dict[str, dict] = {}
analytics_db: dict[str, dict] = {}


def seed_data():
    """Populate databases with realistic test data."""
    now = datetime.now().isoformat()

    # --- Categories ---
    categories = [
        {"id": "cat_electronics", "name": "Electronics", "parent_id": None},
        {"id": "cat_phones", "name": "Smartphones", "parent_id": "cat_electronics"},
        {"id": "cat_laptops", "name": "Laptops", "parent_id": "cat_electronics"},
        {"id": "cat_clothing", "name": "Clothing", "parent_id": None},
        {"id": "cat_mens", "name": "Men's Apparel", "parent_id": "cat_clothing"},
        {"id": "cat_womens", "name": "Women's Apparel", "parent_id": "cat_clothing"},
        {"id": "cat_home", "name": "Home & Garden", "parent_id": None},
        {"id": "cat_furniture", "name": "Furniture", "parent_id": "cat_home"},
        {"id": "cat_sports", "name": "Sports & Outdoors", "parent_id": None},
    ]
    for cat in categories:
        categories_db[cat["id"]] = cat

    # --- Products ---
    products = [
        # Electronics - Phones
        {"id": "prod_iphone15", "name": "iPhone 15 Pro", "description": "Latest Apple smartphone with A17 chip", "price": 999.99, "category_id": "cat_phones", "sku": "APPL-IP15-PRO", "created_at": now},
        {"id": "prod_samsung24", "name": "Samsung Galaxy S24 Ultra", "description": "Premium Android phone with S-Pen", "price": 1199.99, "category_id": "cat_phones", "sku": "SAMS-S24-ULT", "created_at": now},
        {"id": "prod_pixel8", "name": "Google Pixel 8", "description": "Pure Android experience with AI features", "price": 699.99, "category_id": "cat_phones", "sku": "GOOG-PX8-STD", "created_at": now},
        # Electronics - Laptops
        {"id": "prod_macbook", "name": "MacBook Pro 16\"", "description": "M3 Max chip, 36GB RAM, 1TB SSD", "price": 3499.99, "category_id": "cat_laptops", "sku": "APPL-MBP16-M3", "created_at": now},
        {"id": "prod_thinkpad", "name": "ThinkPad X1 Carbon", "description": "Business ultrabook, Intel i7, 32GB RAM", "price": 1899.99, "category_id": "cat_laptops", "sku": "LNVO-X1C-G11", "created_at": now},
        {"id": "prod_xps15", "name": "Dell XPS 15", "description": "Premium Windows laptop with OLED display", "price": 1799.99, "category_id": "cat_laptops", "sku": "DELL-XPS15-24", "created_at": now},
        # Clothing - Men's
        {"id": "prod_tshirt_m", "name": "Classic Cotton T-Shirt", "description": "100% organic cotton, multiple colors", "price": 29.99, "category_id": "cat_mens", "sku": "CLO-TSH-M-001", "created_at": now},
        {"id": "prod_jeans_m", "name": "Slim Fit Denim Jeans", "description": "Stretch denim, dark wash", "price": 79.99, "category_id": "cat_mens", "sku": "CLO-JNS-M-001", "created_at": now},
        {"id": "prod_jacket_m", "name": "Leather Bomber Jacket", "description": "Genuine leather, quilted lining", "price": 299.99, "category_id": "cat_mens", "sku": "CLO-JKT-M-001", "created_at": now},
        # Clothing - Women's
        {"id": "prod_dress_w", "name": "Summer Floral Dress", "description": "Lightweight midi dress, floral print", "price": 89.99, "category_id": "cat_womens", "sku": "CLO-DRS-W-001", "created_at": now},
        {"id": "prod_blazer_w", "name": "Professional Blazer", "description": "Tailored fit, perfect for office", "price": 149.99, "category_id": "cat_womens", "sku": "CLO-BLZ-W-001", "created_at": now},
        # Home & Garden
        {"id": "prod_sofa", "name": "Modern 3-Seater Sofa", "description": "Velvet upholstery, solid wood frame", "price": 1299.99, "category_id": "cat_furniture", "sku": "HOM-SOF-3S-01", "created_at": now},
        {"id": "prod_desk", "name": "Standing Desk Pro", "description": "Electric height adjustable, 60\" wide", "price": 599.99, "category_id": "cat_furniture", "sku": "HOM-DSK-STD-1", "created_at": now},
        {"id": "prod_chair", "name": "Ergonomic Office Chair", "description": "Mesh back, lumbar support, adjustable", "price": 449.99, "category_id": "cat_furniture", "sku": "HOM-CHR-ERG-1", "created_at": now},
        # Sports
        {"id": "prod_bike", "name": "Mountain Bike Pro", "description": "27.5\" wheels, 21-speed, aluminum frame", "price": 899.99, "category_id": "cat_sports", "sku": "SPT-BIK-MTN-1", "created_at": now},
        {"id": "prod_treadmill", "name": "Smart Treadmill", "description": "Foldable, 12 incline levels, HD screen", "price": 1499.99, "category_id": "cat_sports", "sku": "SPT-TRD-SMT-1", "created_at": now},
        {"id": "prod_yoga", "name": "Premium Yoga Mat", "description": "6mm thick, non-slip, eco-friendly", "price": 49.99, "category_id": "cat_sports", "sku": "SPT-YGA-MAT-1", "created_at": now},
    ]
    for prod in products:
        products_db[prod["id"]] = prod
        # Also add inventory
        inventory_db[prod["id"]] = {"product_id": prod["id"], "quantity": 100, "warehouse": "WH-001", "updated_at": now}

    # --- Users ---
    users = [
        {"id": "user_alice", "email": "alice.johnson@email.com", "name": "Alice Johnson", "phone": "+1-555-0101", "created_at": now},
        {"id": "user_bob", "email": "bob.smith@email.com", "name": "Bob Smith", "phone": "+1-555-0102", "created_at": now},
        {"id": "user_carol", "email": "carol.white@email.com", "name": "Carol White", "phone": "+1-555-0103", "created_at": now},
        {"id": "user_david", "email": "david.brown@email.com", "name": "David Brown", "phone": "+1-555-0104", "created_at": now},
        {"id": "user_emma", "email": "emma.davis@email.com", "name": "Emma Davis", "phone": "+1-555-0105", "created_at": now},
    ]
    for user in users:
        users_db[user["id"]] = user

    # --- Addresses ---
    addresses = [
        {"id": "addr_alice_1", "user_id": "user_alice", "street": "123 Oak Street", "city": "San Francisco", "state": "CA", "zip_code": "94102", "country": "US"},
        {"id": "addr_alice_2", "user_id": "user_alice", "street": "456 Pine Ave", "city": "Oakland", "state": "CA", "zip_code": "94612", "country": "US"},
        {"id": "addr_bob_1", "user_id": "user_bob", "street": "789 Maple Drive", "city": "Seattle", "state": "WA", "zip_code": "98101", "country": "US"},
        {"id": "addr_carol_1", "user_id": "user_carol", "street": "321 Elm Road", "city": "Austin", "state": "TX", "zip_code": "78701", "country": "US"},
        {"id": "addr_david_1", "user_id": "user_david", "street": "654 Cedar Lane", "city": "Denver", "state": "CO", "zip_code": "80202", "country": "US"},
        {"id": "addr_emma_1", "user_id": "user_emma", "street": "987 Birch Blvd", "city": "Miami", "state": "FL", "zip_code": "33101", "country": "US"},
    ]
    for addr in addresses:
        addresses_db[addr["id"]] = addr

    # --- Orders (some historical) ---
    orders = [
        {"id": "ord_001", "user_id": "user_alice", "items": [{"product_id": "prod_iphone15", "quantity": 1}], "total": 999.99, "status": "delivered", "created_at": "2024-12-15T10:30:00"},
        {"id": "ord_002", "user_id": "user_alice", "items": [{"product_id": "prod_yoga", "quantity": 2}, {"product_id": "prod_tshirt_m", "quantity": 3}], "total": 189.95, "status": "delivered", "created_at": "2024-12-20T14:15:00"},
        {"id": "ord_003", "user_id": "user_bob", "items": [{"product_id": "prod_macbook", "quantity": 1}], "total": 3499.99, "status": "shipped", "created_at": "2024-12-28T09:00:00"},
        {"id": "ord_004", "user_id": "user_carol", "items": [{"product_id": "prod_sofa", "quantity": 1}, {"product_id": "prod_chair", "quantity": 2}], "total": 2199.97, "status": "processing", "created_at": "2025-01-01T16:45:00"},
        {"id": "ord_005", "user_id": "user_david", "items": [{"product_id": "prod_bike", "quantity": 1}], "total": 899.99, "status": "pending", "created_at": "2025-01-02T08:20:00"},
    ]
    for order in orders:
        orders_db[order["id"]] = order

    # --- Payments ---
    payments = [
        {"id": "pay_001", "order_id": "ord_001", "amount": 999.99, "method": "visa", "status": "completed", "created_at": "2024-12-15T10:31:00"},
        {"id": "pay_002", "order_id": "ord_002", "amount": 189.95, "method": "paypal", "status": "completed", "created_at": "2024-12-20T14:16:00"},
        {"id": "pay_003", "order_id": "ord_003", "amount": 3499.99, "method": "mastercard", "status": "completed", "created_at": "2024-12-28T09:02:00"},
        {"id": "pay_004", "order_id": "ord_004", "amount": 2199.97, "method": "visa", "status": "pending", "created_at": "2025-01-01T16:46:00"},
    ]
    for pay in payments:
        payments_db[pay["id"]] = pay

    # --- Shipments ---
    shipments = [
        {"id": "ship_001", "order_id": "ord_001", "carrier": "fedex", "tracking_number": "FX123456789", "status": "delivered", "created_at": "2024-12-15T12:00:00"},
        {"id": "ship_002", "order_id": "ord_002", "carrier": "ups", "tracking_number": "UP987654321", "status": "delivered", "created_at": "2024-12-20T16:00:00"},
        {"id": "ship_003", "order_id": "ord_003", "carrier": "fedex", "tracking_number": "FX456789123", "status": "in_transit", "created_at": "2024-12-29T10:00:00"},
    ]
    for ship in shipments:
        shipments_db[ship["id"]] = ship

    # --- Reviews ---
    reviews = [
        {"id": "rev_001", "product_id": "prod_iphone15", "user_id": "user_alice", "rating": 5, "comment": "Amazing phone! The camera is incredible.", "created_at": "2024-12-18T09:00:00"},
        {"id": "rev_002", "product_id": "prod_macbook", "user_id": "user_bob", "rating": 5, "comment": "Best laptop I've ever owned. Super fast!", "created_at": "2024-12-30T11:30:00"},
        {"id": "rev_003", "product_id": "prod_yoga", "user_id": "user_alice", "rating": 4, "comment": "Great mat, very comfortable. Slightly heavy.", "created_at": "2024-12-22T15:00:00"},
        {"id": "rev_004", "product_id": "prod_sofa", "user_id": "user_emma", "rating": 3, "comment": "Nice design but delivery took too long.", "created_at": "2024-11-10T14:00:00"},
        {"id": "rev_005", "product_id": "prod_thinkpad", "user_id": "user_david", "rating": 5, "comment": "Perfect for work. Battery lasts all day.", "created_at": "2024-10-05T10:00:00"},
    ]
    for rev in reviews:
        reviews_db[rev["id"]] = rev

    # --- Wishlists ---
    wishlists = [
        {"id": "wish_alice", "user_id": "user_alice", "items": ["prod_macbook", "prod_dress_w", "prod_treadmill"]},
        {"id": "wish_bob", "user_id": "user_bob", "items": ["prod_bike", "prod_desk"]},
        {"id": "wish_carol", "user_id": "user_carol", "items": ["prod_samsung24", "prod_blazer_w"]},
    ]
    for wish in wishlists:
        wishlists_db[wish["id"]] = wish

    # --- Coupons ---
    coupons = [
        {"id": "coup_001", "code": "WELCOME10", "discount_percent": 10, "valid_until": "2025-12-31", "min_order": 50},
        {"id": "coup_002", "code": "SUMMER20", "discount_percent": 20, "valid_until": "2025-08-31", "min_order": 100},
        {"id": "coup_003", "code": "VIP30", "discount_percent": 30, "valid_until": "2025-06-30", "min_order": 500},
        {"id": "coup_004", "code": "FLASH15", "discount_percent": 15, "valid_until": "2025-02-28", "min_order": 75},
    ]
    for coup in coupons:
        coupons_db[coup["id"]] = coup

    # --- Support Tickets ---
    tickets = [
        {"id": "tkt_001", "user_id": "user_carol", "subject": "Order delayed", "description": "My order ord_004 has been processing for 2 days", "status": "open", "priority": "high", "created_at": "2025-01-02T10:00:00"},
        {"id": "tkt_002", "user_id": "user_emma", "subject": "Refund request", "description": "I would like to return the sofa, not satisfied with quality", "status": "open", "priority": "medium", "created_at": "2024-11-15T09:00:00"},
        {"id": "tkt_003", "user_id": "user_bob", "subject": "Tracking not updating", "description": "Shipment FX456789123 hasn't updated in 3 days", "status": "in_progress", "priority": "medium", "created_at": "2025-01-01T14:00:00"},
    ]
    for tkt in tickets:
        support_tickets_db[tkt["id"]] = tkt

    # --- Carts (some with items) ---
    carts = [
        {"user_id": "user_emma", "items": [{"product_id": "prod_pixel8", "quantity": 1}, {"product_id": "prod_yoga", "quantity": 1}], "total": 749.98},
        {"user_id": "user_david", "items": [{"product_id": "prod_desk", "quantity": 1}, {"product_id": "prod_chair", "quantity": 1}], "total": 1049.98},
    ]
    for cart in carts:
        carts_db[cart["user_id"]] = cart


# Run seed on startup
@app.on_event("startup")
def startup_event():
    seed_data()
    print(f"Seeded database: {len(users_db)} users, {len(products_db)} products, {len(orders_db)} orders")


# ============================================================================
# Models
# ============================================================================

class UserCreate(BaseModel):
    email: str
    name: str
    phone: Optional[str] = None

class User(BaseModel):
    id: str
    email: str
    name: str
    phone: Optional[str]
    created_at: str

class ProductCreate(BaseModel):
    name: str
    description: str
    price: float
    category_id: str
    sku: str

class Product(BaseModel):
    id: str
    name: str
    description: str
    price: float
    category_id: str
    sku: str
    created_at: str

class CategoryCreate(BaseModel):
    name: str
    parent_id: Optional[str] = None

class Category(BaseModel):
    id: str
    name: str
    parent_id: Optional[str]

class OrderCreate(BaseModel):
    user_id: str
    items: list[dict]
    shipping_address_id: str

class Order(BaseModel):
    id: str
    user_id: str
    items: list[dict]
    total: float
    status: str
    created_at: str

class CartItem(BaseModel):
    product_id: str
    quantity: int

class Review(BaseModel):
    id: str
    product_id: str
    user_id: str
    rating: int
    comment: str
    created_at: str

class Address(BaseModel):
    id: str
    user_id: str
    street: str
    city: str
    state: str
    zip_code: str
    country: str

class Payment(BaseModel):
    id: str
    order_id: str
    amount: float
    method: str
    status: str
    created_at: str

class Shipment(BaseModel):
    id: str
    order_id: str
    carrier: str
    tracking_number: str
    status: str
    created_at: str

class Coupon(BaseModel):
    id: str
    code: str
    discount_percent: float
    valid_until: str
    min_order: float

class SupportTicket(BaseModel):
    id: str
    user_id: str
    subject: str
    description: str
    status: str
    priority: str
    created_at: str


# ============================================================================
# USER MANAGEMENT (10 endpoints)
# ============================================================================

@app.get("/users", response_model=list[User], tags=["users"])
def list_users(limit: int = Query(50, le=100)):
    """list all users"""
    return list(users_db.values())[:limit]

@app.post("/users", response_model=User, status_code=201, tags=["users"])
def create_user(user: UserCreate):
    """create new user"""
    uid = str(uuid4())[:8]
    new_user = {"id": uid, **user.model_dump(), "created_at": datetime.now().isoformat()}
    users_db[uid] = new_user
    return new_user

@app.get("/users/{user_id}", response_model=User, tags=["users"])
def get_user(user_id: str):
    """get user by id"""
    if user_id not in users_db:
        raise HTTPException(404, "user not found")
    return users_db[user_id]

@app.put("/users/{user_id}", response_model=User, tags=["users"])
def update_user(user_id: str, user: UserCreate):
    """update user"""
    if user_id not in users_db:
        raise HTTPException(404, "user not found")
    users_db[user_id].update(user.model_dump())
    return users_db[user_id]

@app.delete("/users/{user_id}", status_code=204, tags=["users"])
def delete_user(user_id: str):
    """delete user"""
    if user_id not in users_db:
        raise HTTPException(404, "user not found")
    del users_db[user_id]

@app.get("/users/{user_id}/orders", response_model=list[Order], tags=["users"])
def get_user_orders(user_id: str):
    """get orders for user"""
    return [o for o in orders_db.values() if o.get("user_id") == user_id]

@app.get("/users/{user_id}/addresses", response_model=list[Address], tags=["users"])
def get_user_addresses(user_id: str):
    """get addresses for user"""
    return [a for a in addresses_db.values() if a.get("user_id") == user_id]

@app.get("/users/{user_id}/reviews", response_model=list[Review], tags=["users"])
def get_user_reviews(user_id: str):
    """get reviews by user"""
    return [r for r in reviews_db.values() if r.get("user_id") == user_id]

@app.get("/users/{user_id}/wishlist", tags=["users"])
def get_user_wishlist(user_id: str):
    """get user wishlist"""
    return wishlists_db.get(user_id, {"items": []})

@app.post("/users/{user_id}/wishlist/{product_id}", tags=["users"])
def add_to_wishlist(user_id: str, product_id: str):
    """add product to wishlist"""
    if user_id not in wishlists_db:
        wishlists_db[user_id] = {"items": []}
    wishlists_db[user_id]["items"].append(product_id)
    return {"status": "added"}


# ============================================================================
# PRODUCT CATALOG (15 endpoints)
# ============================================================================

@app.get("/products", response_model=list[Product], tags=["products"])
def list_products(
    category_id: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    search: Optional[str] = None,
    limit: int = Query(50, le=100),
):
    """list products with filters"""
    results = list(products_db.values())
    if category_id:
        results = [p for p in results if p.get("category_id") == category_id]
    if min_price:
        results = [p for p in results if p.get("price", 0) >= min_price]
    if max_price:
        results = [p for p in results if p.get("price", 0) <= max_price]
    if search:
        results = [p for p in results if search.lower() in p.get("name", "").lower()]
    return results[:limit]

@app.post("/products", response_model=Product, status_code=201, tags=["products"])
def create_product(product: ProductCreate):
    """create new product"""
    pid = str(uuid4())[:8]
    new_product = {"id": pid, **product.model_dump(), "created_at": datetime.now().isoformat()}
    products_db[pid] = new_product
    return new_product

@app.get("/products/{product_id}", response_model=Product, tags=["products"])
def get_product(product_id: str):
    """get product details"""
    if product_id not in products_db:
        raise HTTPException(404, "product not found")
    return products_db[product_id]

@app.put("/products/{product_id}", response_model=Product, tags=["products"])
def update_product(product_id: str, product: ProductCreate):
    """update product"""
    if product_id not in products_db:
        raise HTTPException(404, "product not found")
    products_db[product_id].update(product.model_dump())
    return products_db[product_id]

@app.delete("/products/{product_id}", status_code=204, tags=["products"])
def delete_product(product_id: str):
    """delete product"""
    if product_id not in products_db:
        raise HTTPException(404, "product not found")
    del products_db[product_id]

@app.get("/products/{product_id}/reviews", response_model=list[Review], tags=["products"])
def get_product_reviews(product_id: str):
    """get reviews for product"""
    return [r for r in reviews_db.values() if r.get("product_id") == product_id]

@app.post("/products/{product_id}/reviews", status_code=201, tags=["products"])
def create_product_review(product_id: str, user_id: str, rating: int, comment: str = ""):
    """add review for product"""
    rid = str(uuid4())[:8]
    review = {"id": rid, "product_id": product_id, "user_id": user_id, "rating": rating, "comment": comment, "created_at": datetime.now().isoformat()}
    reviews_db[rid] = review
    return review

@app.get("/products/{product_id}/related", tags=["products"])
def get_related_products(product_id: str, limit: int = 5):
    """get related products"""
    # Simplified: just return other products
    return list(products_db.values())[:limit]

@app.get("/products/featured", tags=["products"])
def get_featured_products(limit: int = 10):
    """get featured products"""
    return list(products_db.values())[:limit]

@app.get("/products/bestsellers", tags=["products"])
def get_bestsellers(limit: int = 10):
    """get bestselling products"""
    return list(products_db.values())[:limit]

@app.get("/products/new-arrivals", tags=["products"])
def get_new_arrivals(limit: int = 10):
    """get new arrivals"""
    return list(products_db.values())[:limit]

@app.get("/categories", response_model=list[Category], tags=["products"])
def list_categories():
    """list all categories"""
    return list(categories_db.values())

@app.post("/categories", response_model=Category, status_code=201, tags=["products"])
def create_category(category: CategoryCreate):
    """create category"""
    cid = str(uuid4())[:8]
    new_cat = {"id": cid, **category.model_dump()}
    categories_db[cid] = new_cat
    return new_cat

@app.get("/categories/{category_id}", response_model=Category, tags=["products"])
def get_category(category_id: str):
    """get category"""
    if category_id not in categories_db:
        raise HTTPException(404, "category not found")
    return categories_db[category_id]

@app.get("/categories/{category_id}/products", tags=["products"])
def get_category_products(category_id: str, limit: int = 50):
    """get products in category"""
    return [p for p in products_db.values() if p.get("category_id") == category_id][:limit]


# ============================================================================
# SHOPPING CART (8 endpoints)
# ============================================================================

@app.get("/cart/{user_id}", tags=["cart"])
def get_cart(user_id: str):
    """get user cart"""
    return carts_db.get(user_id, {"items": [], "total": 0})

@app.post("/cart/{user_id}/items", tags=["cart"])
def add_to_cart(user_id: str, item: CartItem):
    """add item to cart"""
    if user_id not in carts_db:
        carts_db[user_id] = {"items": [], "total": 0}
    carts_db[user_id]["items"].append(item.model_dump())
    return carts_db[user_id]

@app.put("/cart/{user_id}/items/{product_id}", tags=["cart"])
def update_cart_item(user_id: str, product_id: str, quantity: int):
    """update cart item quantity"""
    if user_id not in carts_db:
        raise HTTPException(404, "cart not found")
    for item in carts_db[user_id]["items"]:
        if item["product_id"] == product_id:
            item["quantity"] = quantity
    return carts_db[user_id]

@app.delete("/cart/{user_id}/items/{product_id}", tags=["cart"])
def remove_from_cart(user_id: str, product_id: str):
    """remove item from cart"""
    if user_id not in carts_db:
        raise HTTPException(404, "cart not found")
    carts_db[user_id]["items"] = [i for i in carts_db[user_id]["items"] if i["product_id"] != product_id]
    return carts_db[user_id]

@app.delete("/cart/{user_id}", tags=["cart"])
def clear_cart(user_id: str):
    """clear entire cart"""
    carts_db[user_id] = {"items": [], "total": 0}
    return {"status": "cleared"}

@app.post("/cart/{user_id}/apply-coupon", tags=["cart"])
def apply_coupon(user_id: str, coupon_code: str):
    """apply coupon to cart"""
    return {"status": "applied", "discount": 10}

@app.get("/cart/{user_id}/summary", tags=["cart"])
def get_cart_summary(user_id: str):
    """get cart summary with totals"""
    cart = carts_db.get(user_id, {"items": []})
    return {"items_count": len(cart["items"]), "subtotal": 0, "tax": 0, "total": 0}

def _calculate_order_total(items: list[dict]) -> float:
    """Calculate total from order items by looking up product prices."""
    total = 0.0
    for item in items:
        product_id = item.get("product_id")
        quantity = item.get("quantity", 1)
        if product_id and product_id in products_db:
            price = products_db[product_id].get("price", 0)
            total += price * quantity
    return total

@app.post("/cart/{user_id}/checkout", tags=["cart"])
def checkout_cart(user_id: str, shipping_address_id: str, payment_method: str):
    """checkout cart and create order"""
    cart = carts_db.get(user_id, {"items": []})
    oid = str(uuid4())[:8]
    total = _calculate_order_total(cart["items"])
    order = {"id": oid, "user_id": user_id, "items": cart["items"], "total": total, "status": "pending", "created_at": datetime.now().isoformat()}
    orders_db[oid] = order
    carts_db[user_id] = {"items": [], "total": 0}
    return order


# ============================================================================
# ORDER MANAGEMENT (12 endpoints)
# ============================================================================

@app.get("/orders", response_model=list[Order], tags=["orders"])
def list_orders(status: Optional[str] = None, limit: int = 50):
    """list all orders"""
    results = list(orders_db.values())
    if status:
        results = [o for o in results if o.get("status") == status]
    return results[:limit]

@app.post("/orders", response_model=Order, status_code=201, tags=["orders"])
def create_order(order: OrderCreate):
    """create new order"""
    oid = str(uuid4())[:8]
    total = _calculate_order_total(order.items)
    new_order = {"id": oid, "user_id": order.user_id, "items": order.items, "total": total, "status": "pending", "created_at": datetime.now().isoformat()}
    orders_db[oid] = new_order
    return new_order

@app.get("/orders/{order_id}", response_model=Order, tags=["orders"])
def get_order(order_id: str):
    """get order details"""
    if order_id not in orders_db:
        raise HTTPException(404, "order not found")
    return orders_db[order_id]

@app.put("/orders/{order_id}/status", tags=["orders"])
def update_order_status(order_id: str, status: str):
    """update order status"""
    if order_id not in orders_db:
        raise HTTPException(404, "order not found")
    orders_db[order_id]["status"] = status
    return orders_db[order_id]

@app.post("/orders/{order_id}/cancel", tags=["orders"])
def cancel_order(order_id: str, reason: str = ""):
    """cancel order"""
    if order_id not in orders_db:
        raise HTTPException(404, "order not found")
    orders_db[order_id]["status"] = "cancelled"
    return orders_db[order_id]

@app.post("/orders/{order_id}/refund", tags=["orders"])
def refund_order(order_id: str, amount: Optional[float] = None):
    """refund order"""
    if order_id not in orders_db:
        raise HTTPException(404, "order not found")
    orders_db[order_id]["status"] = "refunded"
    return {"status": "refunded", "amount": amount or orders_db[order_id].get("total", 0)}

@app.get("/orders/{order_id}/items", tags=["orders"])
def get_order_items(order_id: str):
    """get order items"""
    if order_id not in orders_db:
        raise HTTPException(404, "order not found")
    return orders_db[order_id].get("items", [])

@app.get("/orders/{order_id}/shipment", tags=["orders"])
def get_order_shipment(order_id: str):
    """get shipment for order"""
    shipment = next((s for s in shipments_db.values() if s.get("order_id") == order_id), None)
    if not shipment:
        raise HTTPException(404, "shipment not found")
    return shipment

@app.get("/orders/{order_id}/payment", tags=["orders"])
def get_order_payment(order_id: str):
    """get payment for order"""
    payment = next((p for p in payments_db.values() if p.get("order_id") == order_id), None)
    if not payment:
        raise HTTPException(404, "payment not found")
    return payment

@app.get("/orders/{order_id}/invoice", tags=["orders"])
def get_order_invoice(order_id: str):
    """get invoice for order"""
    if order_id not in orders_db:
        raise HTTPException(404, "order not found")
    return {"order_id": order_id, "invoice_number": f"INV-{order_id}", "total": orders_db[order_id].get("total", 0)}

@app.post("/orders/{order_id}/reorder", tags=["orders"])
def reorder(order_id: str):
    """reorder previous order"""
    if order_id not in orders_db:
        raise HTTPException(404, "order not found")
    old = orders_db[order_id]
    new_id = str(uuid4())[:8]
    new_order = {"id": new_id, "user_id": old["user_id"], "items": old["items"], "total": old["total"], "status": "pending", "created_at": datetime.now().isoformat()}
    orders_db[new_id] = new_order
    return new_order

@app.get("/orders/{order_id}/tracking", tags=["orders"])
def get_order_tracking(order_id: str):
    """get tracking info for order"""
    return {"order_id": order_id, "status": "in_transit", "carrier": "FedEx", "tracking": "1234567890"}


# ============================================================================
# PAYMENTS (8 endpoints)
# ============================================================================

@app.get("/payments", tags=["payments"])
def list_payments(status: Optional[str] = None, limit: int = 50):
    """list payments"""
    results = list(payments_db.values())
    if status:
        results = [p for p in results if p.get("status") == status]
    return results[:limit]

@app.post("/payments", tags=["payments"])
def create_payment(order_id: str, amount: float, method: str):
    """create payment"""
    pid = str(uuid4())[:8]
    payment = {"id": pid, "order_id": order_id, "amount": amount, "method": method, "status": "pending", "created_at": datetime.now().isoformat()}
    payments_db[pid] = payment
    return payment

@app.get("/payments/{payment_id}", tags=["payments"])
def get_payment(payment_id: str):
    """get payment details"""
    if payment_id not in payments_db:
        raise HTTPException(404, "payment not found")
    return payments_db[payment_id]

@app.post("/payments/{payment_id}/capture", tags=["payments"])
def capture_payment(payment_id: str):
    """capture authorized payment"""
    if payment_id not in payments_db:
        raise HTTPException(404, "payment not found")
    payments_db[payment_id]["status"] = "captured"
    return payments_db[payment_id]

@app.post("/payments/{payment_id}/refund", tags=["payments"])
def refund_payment(payment_id: str, amount: Optional[float] = None):
    """refund payment"""
    if payment_id not in payments_db:
        raise HTTPException(404, "payment not found")
    payments_db[payment_id]["status"] = "refunded"
    return payments_db[payment_id]

@app.post("/payments/{payment_id}/void", tags=["payments"])
def void_payment(payment_id: str):
    """void pending payment"""
    if payment_id not in payments_db:
        raise HTTPException(404, "payment not found")
    payments_db[payment_id]["status"] = "voided"
    return payments_db[payment_id]

@app.get("/payments/methods", tags=["payments"])
def list_payment_methods():
    """list available payment methods"""
    return [{"id": "card", "name": "Credit Card"}, {"id": "paypal", "name": "PayPal"}, {"id": "apple_pay", "name": "Apple Pay"}]

@app.post("/payments/validate-card", tags=["payments"])
def validate_card(card_number: str, exp_month: int, exp_year: int, cvv: str):
    """validate credit card"""
    return {"valid": True, "card_type": "visa"}


# ============================================================================
# SHIPPING (10 endpoints)
# ============================================================================

@app.get("/shipments", tags=["shipping"])
def list_shipments(status: Optional[str] = None, limit: int = 50):
    """list shipments"""
    results = list(shipments_db.values())
    if status:
        results = [s for s in results if s.get("status") == status]
    return results[:limit]

@app.post("/shipments", tags=["shipping"])
def create_shipment(order_id: str, carrier: str):
    """create shipment"""
    sid = str(uuid4())[:8]
    shipment = {"id": sid, "order_id": order_id, "carrier": carrier, "tracking_number": f"TRK{sid}", "status": "pending", "created_at": datetime.now().isoformat()}
    shipments_db[sid] = shipment
    return shipment

@app.get("/shipments/{shipment_id}", tags=["shipping"])
def get_shipment(shipment_id: str):
    """get shipment details"""
    if shipment_id not in shipments_db:
        raise HTTPException(404, "shipment not found")
    return shipments_db[shipment_id]

@app.put("/shipments/{shipment_id}/status", tags=["shipping"])
def update_shipment_status(shipment_id: str, status: str):
    """update shipment status"""
    if shipment_id not in shipments_db:
        raise HTTPException(404, "shipment not found")
    shipments_db[shipment_id]["status"] = status
    return shipments_db[shipment_id]

@app.get("/shipments/{shipment_id}/tracking", tags=["shipping"])
def get_shipment_tracking(shipment_id: str):
    """get tracking updates"""
    return {"shipment_id": shipment_id, "events": [{"status": "shipped", "timestamp": datetime.now().isoformat()}]}

@app.post("/shipments/{shipment_id}/label", tags=["shipping"])
def generate_shipping_label(shipment_id: str):
    """generate shipping label"""
    return {"shipment_id": shipment_id, "label_url": f"https://labels.example.com/{shipment_id}.pdf"}

@app.get("/shipping/rates", tags=["shipping"])
def get_shipping_rates(origin_zip: str, dest_zip: str, weight: float):
    """get shipping rates"""
    return [{"carrier": "FedEx", "service": "Ground", "rate": 9.99}, {"carrier": "UPS", "service": "Ground", "rate": 10.99}]

@app.get("/shipping/carriers", tags=["shipping"])
def list_carriers():
    """list shipping carriers"""
    return [{"id": "fedex", "name": "FedEx"}, {"id": "ups", "name": "UPS"}, {"id": "usps", "name": "USPS"}]

@app.post("/shipping/validate-address", tags=["shipping"])
def validate_address(street: str, city: str, state: str, zip_code: str):
    """validate shipping address"""
    return {"valid": True, "normalized": {"street": street, "city": city, "state": state, "zip": zip_code}}

@app.get("/shipping/estimate", tags=["shipping"])
def estimate_delivery(origin_zip: str, dest_zip: str, carrier: str):
    """estimate delivery date"""
    return {"carrier": carrier, "estimated_days": 5, "estimated_date": "2025-01-05"}


# ============================================================================
# ADDRESSES (6 endpoints)
# ============================================================================

@app.get("/addresses", tags=["addresses"])
def list_addresses(user_id: Optional[str] = None):
    """list addresses"""
    results = list(addresses_db.values())
    if user_id:
        results = [a for a in results if a.get("user_id") == user_id]
    return results

@app.post("/addresses", tags=["addresses"])
def create_address(user_id: str, street: str, city: str, state: str, zip_code: str, country: str = "US"):
    """create address"""
    aid = str(uuid4())[:8]
    address = {"id": aid, "user_id": user_id, "street": street, "city": city, "state": state, "zip_code": zip_code, "country": country}
    addresses_db[aid] = address
    return address

@app.get("/addresses/{address_id}", tags=["addresses"])
def get_address(address_id: str):
    """get address"""
    if address_id not in addresses_db:
        raise HTTPException(404, "address not found")
    return addresses_db[address_id]

@app.put("/addresses/{address_id}", tags=["addresses"])
def update_address(address_id: str, street: str, city: str, state: str, zip_code: str):
    """update address"""
    if address_id not in addresses_db:
        raise HTTPException(404, "address not found")
    addresses_db[address_id].update({"street": street, "city": city, "state": state, "zip_code": zip_code})
    return addresses_db[address_id]

@app.delete("/addresses/{address_id}", status_code=204, tags=["addresses"])
def delete_address(address_id: str):
    """delete address"""
    if address_id not in addresses_db:
        raise HTTPException(404, "address not found")
    del addresses_db[address_id]

@app.post("/addresses/{address_id}/set-default", tags=["addresses"])
def set_default_address(address_id: str):
    """set as default address"""
    return {"address_id": address_id, "is_default": True}


# ============================================================================
# COUPONS & PROMOTIONS (8 endpoints)
# ============================================================================

@app.get("/coupons", tags=["promotions"])
def list_coupons(active_only: bool = True):
    """list coupons"""
    return list(coupons_db.values())

@app.post("/coupons", tags=["promotions"])
def create_coupon(code: str, discount_percent: float, valid_until: str, min_order: float = 0):
    """create coupon"""
    cid = str(uuid4())[:8]
    coupon = {"id": cid, "code": code, "discount_percent": discount_percent, "valid_until": valid_until, "min_order": min_order}
    coupons_db[cid] = coupon
    return coupon

@app.get("/coupons/{coupon_id}", tags=["promotions"])
def get_coupon(coupon_id: str):
    """get coupon details"""
    if coupon_id not in coupons_db:
        raise HTTPException(404, "coupon not found")
    return coupons_db[coupon_id]

@app.delete("/coupons/{coupon_id}", status_code=204, tags=["promotions"])
def delete_coupon(coupon_id: str):
    """delete coupon"""
    if coupon_id not in coupons_db:
        raise HTTPException(404, "coupon not found")
    del coupons_db[coupon_id]

@app.post("/coupons/validate", tags=["promotions"])
def validate_coupon(code: str, order_total: float):
    """validate coupon code"""
    coupon = next((c for c in coupons_db.values() if c["code"] == code), None)
    if not coupon:
        return {"valid": False, "reason": "not found"}
    return {"valid": True, "discount": coupon["discount_percent"]}

@app.get("/promotions", tags=["promotions"])
def list_promotions():
    """list active promotions"""
    return [{"id": "summer-sale", "name": "Summer Sale", "discount": 20}]

@app.get("/promotions/{promo_id}", tags=["promotions"])
def get_promotion(promo_id: str):
    """get promotion details"""
    return {"id": promo_id, "name": "Summer Sale", "discount": 20, "valid_until": "2025-08-31"}

@app.get("/promotions/{promo_id}/products", tags=["promotions"])
def get_promotion_products(promo_id: str):
    """get products in promotion"""
    return list(products_db.values())[:10]


# ============================================================================
# INVENTORY (8 endpoints)
# ============================================================================

@app.get("/inventory", tags=["inventory"])
def list_inventory(low_stock: bool = False):
    """list inventory"""
    results = list(inventory_db.values())
    if low_stock:
        results = [i for i in results if i.get("quantity", 0) < 10]
    return results

@app.get("/inventory/{product_id}", tags=["inventory"])
def get_inventory(product_id: str):
    """get inventory for product"""
    return inventory_db.get(product_id, {"product_id": product_id, "quantity": 0, "reserved": 0})

@app.put("/inventory/{product_id}", tags=["inventory"])
def update_inventory(product_id: str, quantity: int):
    """update inventory quantity"""
    inventory_db[product_id] = {"product_id": product_id, "quantity": quantity, "reserved": 0}
    return inventory_db[product_id]

@app.post("/inventory/{product_id}/reserve", tags=["inventory"])
def reserve_inventory(product_id: str, quantity: int):
    """reserve inventory"""
    if product_id not in inventory_db:
        inventory_db[product_id] = {"product_id": product_id, "quantity": 100, "reserved": 0}
    inventory_db[product_id]["reserved"] += quantity
    return inventory_db[product_id]

@app.post("/inventory/{product_id}/release", tags=["inventory"])
def release_inventory(product_id: str, quantity: int):
    """release reserved inventory"""
    if product_id in inventory_db:
        inventory_db[product_id]["reserved"] = max(0, inventory_db[product_id]["reserved"] - quantity)
    return inventory_db.get(product_id, {})

@app.post("/inventory/{product_id}/adjust", tags=["inventory"])
def adjust_inventory(product_id: str, delta: int, reason: str = ""):
    """adjust inventory with reason"""
    if product_id not in inventory_db:
        inventory_db[product_id] = {"product_id": product_id, "quantity": 0, "reserved": 0}
    inventory_db[product_id]["quantity"] += delta
    return inventory_db[product_id]

@app.get("/inventory/alerts", tags=["inventory"])
def get_inventory_alerts():
    """get low stock alerts"""
    return [i for i in inventory_db.values() if i.get("quantity", 0) < 10]

@app.get("/inventory/report", tags=["inventory"])
def get_inventory_report():
    """get inventory report"""
    total = sum(i.get("quantity", 0) for i in inventory_db.values())
    return {"total_items": total, "low_stock_count": 0, "out_of_stock_count": 0}


# ============================================================================
# SUPPORT (8 endpoints)
# ============================================================================

@app.get("/support/tickets", tags=["support"])
def list_tickets(status: Optional[str] = None, priority: Optional[str] = None):
    """list support tickets"""
    results = list(support_tickets_db.values())
    if status:
        results = [t for t in results if t.get("status") == status]
    if priority:
        results = [t for t in results if t.get("priority") == priority]
    return results

@app.post("/support/tickets", tags=["support"])
def create_ticket(user_id: str, subject: str, description: str, priority: str = "normal"):
    """create support ticket"""
    tid = str(uuid4())[:8]
    ticket = {"id": tid, "user_id": user_id, "subject": subject, "description": description, "status": "open", "priority": priority, "created_at": datetime.now().isoformat()}
    support_tickets_db[tid] = ticket
    return ticket

@app.get("/support/tickets/{ticket_id}", tags=["support"])
def get_ticket(ticket_id: str):
    """get ticket details"""
    if ticket_id not in support_tickets_db:
        raise HTTPException(404, "ticket not found")
    return support_tickets_db[ticket_id]

@app.put("/support/tickets/{ticket_id}/status", tags=["support"])
def update_ticket_status(ticket_id: str, status: str):
    """update ticket status"""
    if ticket_id not in support_tickets_db:
        raise HTTPException(404, "ticket not found")
    support_tickets_db[ticket_id]["status"] = status
    return support_tickets_db[ticket_id]

@app.post("/support/tickets/{ticket_id}/reply", tags=["support"])
def reply_to_ticket(ticket_id: str, message: str):
    """reply to ticket"""
    return {"ticket_id": ticket_id, "reply": message, "timestamp": datetime.now().isoformat()}

@app.post("/support/tickets/{ticket_id}/close", tags=["support"])
def close_ticket(ticket_id: str, resolution: str = ""):
    """close ticket"""
    if ticket_id not in support_tickets_db:
        raise HTTPException(404, "ticket not found")
    support_tickets_db[ticket_id]["status"] = "closed"
    return support_tickets_db[ticket_id]

@app.get("/support/faq", tags=["support"])
def list_faq():
    """list FAQ"""
    return [{"q": "How to return?", "a": "..."}, {"q": "Shipping times?", "a": "..."}]

@app.get("/support/contact", tags=["support"])
def get_contact_info():
    """get contact info"""
    return {"email": "support@example.com", "phone": "1-800-EXAMPLE", "hours": "9am-5pm EST"}


# ============================================================================
# ANALYTICS (6 endpoints)
# ============================================================================

@app.get("/analytics/sales", tags=["analytics"])
def get_sales_analytics(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """get sales analytics"""
    return {"total_sales": 150000, "orders_count": 1500, "avg_order_value": 100}

@app.get("/analytics/products", tags=["analytics"])
def get_product_analytics(limit: int = 10):
    """get product analytics"""
    return {"top_products": [], "low_performers": []}

@app.get("/analytics/customers", tags=["analytics"])
def get_customer_analytics():
    """get customer analytics"""
    return {"total_customers": 5000, "new_this_month": 200, "returning_rate": 0.45}

@app.get("/analytics/revenue", tags=["analytics"])
def get_revenue_analytics(period: str = "month"):
    """get revenue analytics"""
    return {"period": period, "revenue": 50000, "growth": 0.15}

@app.get("/analytics/inventory", tags=["analytics"])
def get_inventory_analytics():
    """get inventory analytics"""
    return {"total_value": 250000, "turnover_rate": 4.5}

@app.get("/analytics/dashboard", tags=["analytics"])
def get_dashboard():
    """get dashboard summary"""
    return {"sales_today": 5000, "orders_today": 50, "visitors_today": 1000}


# ============================================================================
# NOTIFICATIONS (5 endpoints)
# ============================================================================

@app.get("/notifications/{user_id}", tags=["notifications"])
def get_user_notifications(user_id: str, unread_only: bool = False):
    """get user notifications"""
    return notifications_db.get(user_id, [])

@app.post("/notifications/{user_id}", tags=["notifications"])
def create_notification(user_id: str, title: str, message: str, notification_type: str = "info"):
    """create notification"""
    if user_id not in notifications_db:
        notifications_db[user_id] = []
    notif = {"id": str(uuid4())[:8], "title": title, "message": message, "type": notification_type, "read": False}
    notifications_db[user_id].append(notif)
    return notif

@app.put("/notifications/{user_id}/{notification_id}/read", tags=["notifications"])
def mark_notification_read(user_id: str, notification_id: str):
    """mark notification as read"""
    return {"notification_id": notification_id, "read": True}

@app.delete("/notifications/{user_id}/{notification_id}", tags=["notifications"])
def delete_notification(user_id: str, notification_id: str):
    """delete notification"""
    return {"status": "deleted"}

@app.post("/notifications/{user_id}/mark-all-read", tags=["notifications"])
def mark_all_read(user_id: str):
    """mark all notifications as read"""
    return {"status": "all marked read"}


# ============================================================================
# HEALTH (2 endpoints)
# ============================================================================

@app.get("/health", tags=["health"])
def health_check():
    """health check"""
    return {"status": "ok"}

@app.get("/health/detailed", tags=["health"])
def detailed_health():
    """detailed health check"""
    return {"status": "ok", "database": "connected", "cache": "connected"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)
