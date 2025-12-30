"""Messy API for testing OMCP filtering and LLM description rewriting.

This API intentionally has:
- Unnecessary internal/debug routes that should be excluded
- Poor/vague descriptions that need LLM improvement
- Redundant endpoints
- Mixed quality documentation
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Header
from pydantic import BaseModel, Field

app = FastAPI(
    title="Acme Widget Store API",
    description="API for widgets and stuff",
    version="2.1.0",
)

# In-memory databases
widgets_db: dict[str, dict] = {}
orders_db: dict[str, dict] = {}
reviews_db: dict[str, dict] = {}
debug_logs: list[dict] = []
cache_store: dict[str, str] = {}


# ============================================================================
# Models
# ============================================================================

class WidgetCreate(BaseModel):
    name: str = Field(..., description="the name")
    price: float = Field(..., description="how much it costs")
    category: str = Field("general", description="category thing")
    stock: int = Field(0, description="number")


class Widget(BaseModel):
    id: str
    name: str
    price: float
    category: str
    stock: int
    created: str


class OrderCreate(BaseModel):
    widget_id: str = Field(..., description="id of widget")
    quantity: int = Field(1, description="qty")
    shipping_address: str = Field(..., description="address for shipping")


class Order(BaseModel):
    id: str
    widget_id: str
    quantity: int
    shipping_address: str
    status: str
    total: float
    created: str


class ReviewCreate(BaseModel):
    widget_id: str = Field(..., description="widget")
    rating: int = Field(..., description="1-5")
    comment: str = Field("", description="text")


class Review(BaseModel):
    id: str
    widget_id: str
    rating: int
    comment: str
    created: str


# ============================================================================
# Widget Endpoints (Core - should be included)
# ============================================================================

@app.get("/widgets", response_model=list[Widget], tags=["widgets"])
def get_widgets(
    category: Optional[str] = Query(None, description="filter"),
    min_price: Optional[float] = Query(None, description="min"),
    max_price: Optional[float] = Query(None, description="max"),
    in_stock: Optional[bool] = Query(None, description="stock filter"),
):
    """gets widgets from the database"""
    result = list(widgets_db.values())
    if category:
        result = [w for w in result if w["category"] == category]
    if min_price is not None:
        result = [w for w in result if w["price"] >= min_price]
    if max_price is not None:
        result = [w for w in result if w["price"] <= max_price]
    if in_stock is not None:
        result = [w for w in result if (w["stock"] > 0) == in_stock]
    return result


@app.post("/widgets", response_model=Widget, status_code=201, tags=["widgets"])
def create_widget(widget: WidgetCreate):
    """make a new widget"""
    widget_id = str(uuid4())[:8]
    new_widget = {
        "id": widget_id,
        "name": widget.name,
        "price": widget.price,
        "category": widget.category,
        "stock": widget.stock,
        "created": datetime.now().isoformat(),
    }
    widgets_db[widget_id] = new_widget
    return new_widget


@app.get("/widgets/{widget_id}", response_model=Widget, tags=["widgets"])
def get_widget(widget_id: str):
    """get one widget by its id"""
    if widget_id not in widgets_db:
        raise HTTPException(status_code=404, detail="not found")
    return widgets_db[widget_id]


@app.put("/widgets/{widget_id}", response_model=Widget, tags=["widgets"])
def update_widget(widget_id: str, widget: WidgetCreate):
    """update widget data"""
    if widget_id not in widgets_db:
        raise HTTPException(status_code=404, detail="not found")
    widgets_db[widget_id].update({
        "name": widget.name,
        "price": widget.price,
        "category": widget.category,
        "stock": widget.stock,
    })
    return widgets_db[widget_id]


@app.delete("/widgets/{widget_id}", status_code=204, tags=["widgets"])
def delete_widget(widget_id: str):
    """remove a widget"""
    if widget_id not in widgets_db:
        raise HTTPException(status_code=404, detail="not found")
    del widgets_db[widget_id]


@app.patch("/widgets/{widget_id}/stock", response_model=Widget, tags=["widgets"])
def adjust_stock(widget_id: str, delta: int = Query(..., description="change amount")):
    """change stock level"""
    if widget_id not in widgets_db:
        raise HTTPException(status_code=404, detail="not found")
    widgets_db[widget_id]["stock"] += delta
    return widgets_db[widget_id]


# ============================================================================
# Order Endpoints (Core - should be included)
# ============================================================================

@app.get("/orders", response_model=list[Order], tags=["orders"])
def list_orders(
    status: Optional[str] = Query(None, description="order status filter"),
):
    """get all orders"""
    result = list(orders_db.values())
    if status:
        result = [o for o in result if o["status"] == status]
    return result


@app.post("/orders", response_model=Order, status_code=201, tags=["orders"])
def create_order(order: OrderCreate):
    """place an order for widgets"""
    if order.widget_id not in widgets_db:
        raise HTTPException(status_code=400, detail="widget doesnt exist")
    
    widget = widgets_db[order.widget_id]
    if widget["stock"] < order.quantity:
        raise HTTPException(status_code=400, detail="not enough stock")
    
    order_id = str(uuid4())[:8]
    new_order = {
        "id": order_id,
        "widget_id": order.widget_id,
        "quantity": order.quantity,
        "shipping_address": order.shipping_address,
        "status": "pending",
        "total": widget["price"] * order.quantity,
        "created": datetime.now().isoformat(),
    }
    orders_db[order_id] = new_order
    widgets_db[order.widget_id]["stock"] -= order.quantity
    return new_order


@app.get("/orders/{order_id}", response_model=Order, tags=["orders"])
def get_order(order_id: str):
    """fetch order details"""
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="order not found")
    return orders_db[order_id]


@app.post("/orders/{order_id}/cancel", response_model=Order, tags=["orders"])
def cancel_order(order_id: str):
    """cancel an order if possible"""
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="order not found")
    order = orders_db[order_id]
    if order["status"] != "pending":
        raise HTTPException(status_code=400, detail="cant cancel")
    order["status"] = "cancelled"
    # Restore stock
    widgets_db[order["widget_id"]]["stock"] += order["quantity"]
    return order


# ============================================================================
# Review Endpoints (Core - should be included)
# ============================================================================

@app.get("/reviews", response_model=list[Review], tags=["reviews"])
def get_reviews(widget_id: Optional[str] = Query(None, description="filter by widget")):
    """list reviews"""
    result = list(reviews_db.values())
    if widget_id:
        result = [r for r in result if r["widget_id"] == widget_id]
    return result


@app.post("/reviews", response_model=Review, status_code=201, tags=["reviews"])
def create_review(review: ReviewCreate):
    """add a review"""
    if review.widget_id not in widgets_db:
        raise HTTPException(status_code=400, detail="widget not found")
    if not 1 <= review.rating <= 5:
        raise HTTPException(status_code=400, detail="rating must be 1-5")
    
    review_id = str(uuid4())[:8]
    new_review = {
        "id": review_id,
        "widget_id": review.widget_id,
        "rating": review.rating,
        "comment": review.comment,
        "created": datetime.now().isoformat(),
    }
    reviews_db[review_id] = new_review
    return new_review


# ============================================================================
# Debug/Internal Endpoints (Should be EXCLUDED)
# ============================================================================

@app.get("/debug/logs", tags=["debug"])
def get_debug_logs(limit: int = Query(100, description="how many")):
    """internal debug log viewer - dont use in prod"""
    return debug_logs[-limit:]


@app.post("/debug/logs", tags=["debug"])
def add_debug_log(message: str = Query(..., description="log msg")):
    """add debug log entry"""
    debug_logs.append({
        "message": message,
        "timestamp": datetime.now().isoformat(),
    })
    return {"status": "logged"}


@app.delete("/debug/logs", tags=["debug"])
def clear_debug_logs():
    """wipe all debug logs"""
    debug_logs.clear()
    return {"status": "cleared"}


@app.get("/internal/cache", tags=["internal"])
def get_cache():
    """dump cache contents"""
    return cache_store


@app.post("/internal/cache/{key}", tags=["internal"])
def set_cache(key: str, value: str = Query(..., description="val")):
    """set cache value"""
    cache_store[key] = value
    return {"key": key, "value": value}


@app.delete("/internal/cache", tags=["internal"])
def flush_cache():
    """clear all cache"""
    cache_store.clear()
    return {"status": "flushed"}


@app.get("/internal/metrics", tags=["internal"])
def get_metrics():
    """internal metrics endpoint"""
    return {
        "widgets_count": len(widgets_db),
        "orders_count": len(orders_db),
        "reviews_count": len(reviews_db),
        "cache_size": len(cache_store),
        "log_count": len(debug_logs),
    }


# ============================================================================
# Admin Endpoints (Should be EXCLUDED - dangerous operations)
# ============================================================================

@app.post("/admin/reset", tags=["admin"])
def admin_reset():
    """DANGEROUS: wipes everything"""
    widgets_db.clear()
    orders_db.clear()
    reviews_db.clear()
    debug_logs.clear()
    cache_store.clear()
    return {"status": "everything deleted"}


@app.post("/admin/seed", tags=["admin"])
def admin_seed():
    """seed database with test data"""
    # Add some widgets
    for i in range(5):
        wid = f"seed-{i}"
        widgets_db[wid] = {
            "id": wid,
            "name": f"Test Widget {i}",
            "price": 10.0 * (i + 1),
            "category": ["electronics", "home", "toys"][i % 3],
            "stock": 100,
            "created": datetime.now().isoformat(),
        }
    return {"status": "seeded", "widgets": len(widgets_db)}


@app.get("/admin/export", tags=["admin"])
def admin_export():
    """export all data - internal only"""
    return {
        "widgets": list(widgets_db.values()),
        "orders": list(orders_db.values()),
        "reviews": list(reviews_db.values()),
    }


# ============================================================================
# Health/Status Endpoints (Maybe include, maybe not)
# ============================================================================

@app.get("/health", tags=["health"])
def health_check():
    """basic health check"""
    return {"status": "ok"}


@app.get("/health/detailed", tags=["health"])
def detailed_health():
    """detailed health with db stats"""
    return {
        "status": "ok",
        "database": "connected",
        "widgets": len(widgets_db),
        "orders": len(orders_db),
    }


@app.get("/", tags=["meta"])
def root():
    """api root"""
    return {"api": "Acme Widget Store", "version": "2.1.0"}


@app.get("/docs-redirect", tags=["meta"])
def docs_redirect():
    """redirects to documentation"""
    return {"redirect": "/docs"}


# ============================================================================
# Duplicate/Legacy Endpoints (Should be EXCLUDED - redundant)
# ============================================================================

@app.get("/v1/widgets", response_model=list[Widget], tags=["legacy"])
def get_widgets_v1():
    """DEPRECATED: old widgets endpoint, use /widgets instead"""
    return list(widgets_db.values())


@app.get("/v1/orders", response_model=list[Order], tags=["legacy"])
def get_orders_v1():
    """DEPRECATED: old orders endpoint"""
    return list(orders_db.values())


@app.get("/api/widgets", response_model=list[Widget], tags=["legacy"])
def get_widgets_alt():
    """alternative path, same as /widgets"""
    return list(widgets_db.values())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
