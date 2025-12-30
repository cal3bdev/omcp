"""Test prompts for MCP E-Commerce Agent.

Organized by complexity:
- Simple: Single tool call
- Medium: 2-3 tool calls in sequence
- Complex: Multiple tools across different modules

Each prompt includes expected modules to help verify routing.
"""

# Simple prompts - single tool call
SIMPLE_PROMPTS = [
    {
        "id": "simple_1",
        "prompt": "List all users in the system",
        "expected_modules": ["user_management"],
        "expected_tools": ["list_users"],
        "description": "Basic list operation",
    },
    {
        "id": "simple_2", 
        "prompt": "Get the details for product ID 'prod_123'",
        "expected_modules": ["product_management"],
        "expected_tools": ["get_product"],
        "description": "Single item lookup",
    },
    {
        "id": "simple_3",
        "prompt": "Show me all available categories",
        "expected_modules": ["product_catalog"],
        "expected_tools": ["list_categories"],
        "description": "Category listing",
    },
    {
        "id": "simple_4",
        "prompt": "Check the health status of the API",
        "expected_modules": ["health_monitoring"],
        "expected_tools": ["health_check"],
        "description": "Health check",
    },
    {
        "id": "simple_5",
        "prompt": "What payment methods are available?",
        "expected_modules": ["payment_processing"],
        "expected_tools": ["list_payment_methods"],
        "description": "Payment methods listing",
    },
]

# Medium prompts - 2-3 related tool calls
MEDIUM_PROMPTS = [
    {
        "id": "medium_1",
        "prompt": "Get user 'user_001' and show all their orders",
        "expected_modules": ["user_management", "order_management"],
        "expected_tools": ["get_user", "get_user_orders"],
        "description": "User + their orders",
    },
    {
        "id": "medium_2",
        "prompt": "Find the product 'prod_456' and show its reviews",
        "expected_modules": ["product_management"],
        "expected_tools": ["get_product", "get_product_reviews"],
        "description": "Product + reviews",
    },
    {
        "id": "medium_3",
        "prompt": "Show me the cart for user 'user_002' and get the summary with totals",
        "expected_modules": ["cart_management"],
        "expected_tools": ["get_cart", "get_cart_summary"],
        "description": "Cart details + summary",
    },
    {
        "id": "medium_4",
        "prompt": "Get order 'ord_789' details including its shipment tracking",
        "expected_modules": ["order_management", "shipping_management"],
        "expected_tools": ["get_order", "get_order_shipment"],
        "description": "Order + shipment",
    },
    {
        "id": "medium_5",
        "prompt": "List all support tickets and show the FAQ",
        "expected_modules": ["support_ticket_management", "support_operations"],
        "expected_tools": ["list_tickets", "list_faq"],
        "description": "Support overview",
    },
]

# Complex prompts - multiple tools across different modules
COMPLEX_PROMPTS = [
    {
        "id": "complex_1",
        "prompt": """Process a refund for order 'ord_123':
        1. First get the order details
        2. Get the payment information for the order
        3. Process the refund on that payment
        4. Update the order status to 'refunded'""",
        "expected_modules": ["order_management", "payment_processing"],
        "expected_tools": ["get_order", "get_order_payment", "refund_payment", "update_order_status"],
        "description": "Full refund workflow",
    },
    {
        "id": "complex_2",
        "prompt": """Complete a checkout for user 'user_005':
        1. Get their cart contents and summary
        2. Get their default shipping address  
        3. Validate the shipping address
        4. Calculate shipping rates from zip 90210 to their zip
        5. Process the checkout""",
        "expected_modules": ["cart_management", "address_management", "shipping_management"],
        "expected_tools": ["get_cart", "get_cart_summary", "list_addresses", "validate_address", "get_shipping_rates", "checkout_cart"],
        "description": "Full checkout workflow",
    },
    {
        "id": "complex_3",
        "prompt": """Create a support ticket for user 'user_010' about a delayed shipment:
        1. Get the user's recent orders
        2. Get the shipment tracking for their latest order
        3. Create a support ticket with the shipment details
        4. Send them a notification about the ticket""",
        "expected_modules": ["user_management", "order_management", "shipping_management", "support_ticket_management", "notification_management"],
        "expected_tools": ["get_user_orders", "get_order_shipment", "create_ticket", "create_notification"],
        "description": "Support ticket with context",
    },
    {
        "id": "complex_4",
        "prompt": """Generate a sales report:
        1. Get the sales analytics for the current period
        2. Get the top performing products
        3. Get the revenue breakdown
        4. Get inventory alerts for low stock items
        5. Summarize with the dashboard""",
        "expected_modules": ["analytics_reporting", "inventory_management"],
        "expected_tools": ["get_sales_analytics", "get_product_analytics", "get_revenue_analytics", "get_inventory_alerts", "get_dashboard"],
        "description": "Analytics dashboard",
    },
    {
        "id": "complex_5",
        "prompt": """Set up a new promotion:
        1. List current active promotions
        2. List current coupons
        3. Create a new coupon code 'NEWYEAR25' with 25% off, valid until 2025-01-31
        4. Validate the new coupon works for a $100 order""",
        "expected_modules": ["promotion_management", "coupon_management"],
        "expected_tools": ["list_promotions", "list_coupons", "create_coupon", "validate_coupon"],
        "description": "Promotion setup",
    },
]

# All prompts for iteration
ALL_PROMPTS = SIMPLE_PROMPTS + MEDIUM_PROMPTS + COMPLEX_PROMPTS


def get_prompt_by_id(prompt_id: str) -> dict | None:
    """Get a specific prompt by ID."""
    for prompt in ALL_PROMPTS:
        if prompt["id"] == prompt_id:
            return prompt
    return None


def get_prompts_by_complexity(complexity: str) -> list[dict]:
    """Get prompts by complexity level."""
    if complexity == "simple":
        return SIMPLE_PROMPTS
    elif complexity == "medium":
        return MEDIUM_PROMPTS
    elif complexity == "complex":
        return COMPLEX_PROMPTS
    else:
        return ALL_PROMPTS
