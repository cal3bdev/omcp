# MegaStore Agent - Example Prompts

Multi-module prompt examples for testing the OMCP Hub agent with seeded data.

## Seed Data Overview

### Users
| ID | Name | Email | City |
|----|------|-------|------|
| user_alice | Alice Johnson | alice.johnson@email.com | San Francisco |
| user_bob | Bob Smith | bob.smith@email.com | Seattle |
| user_carol | Carol White | carol.white@email.com | Austin |
| user_david | David Brown | david.brown@email.com | Denver |
| user_emma | Emma Davis | emma.davis@email.com | Miami |

### Products (17 items)
- **Phones**: iPhone 15 Pro ($999.99), Samsung Galaxy S24 Ultra ($1199.99), Google Pixel 8 ($699.99)
- **Laptops**: MacBook Pro 16" ($3499.99), ThinkPad X1 Carbon ($1899.99), Dell XPS 15 ($1799.99)
- **Men's Clothing**: T-Shirt ($29.99), Jeans ($79.99), Leather Jacket ($299.99)
- **Women's Clothing**: Floral Dress ($89.99), Professional Blazer ($149.99)
- **Furniture**: 3-Seater Sofa ($1299.99), Standing Desk ($599.99), Ergonomic Chair ($449.99)
- **Sports**: Mountain Bike ($899.99), Smart Treadmill ($1499.99), Yoga Mat ($49.99)

### Active Orders
- **ord_003** (Bob): MacBook Pro - shipped, in transit
- **ord_004** (Carol): Sofa + 2 Chairs - processing (has support ticket)
- **ord_005** (David): Mountain Bike - pending payment

### Support Tickets
- **tkt_001**: Carol's delayed order (high priority)
- **tkt_002**: Emma's refund request for sofa
- **tkt_003**: Bob's tracking not updating

### Coupons
- WELCOME10 (10% off, min $50)
- SUMMER20 (20% off, min $100)
- VIP30 (30% off, min $500)
- FLASH15 (15% off, min $75)

---

## Simple Queries (Single Module)

### User Management
```
List all users in the system
```

```
Find Bob Smith's email address
```

```
What is Alice Johnson's phone number?
```

### Product Catalog
```
Show me all laptops you have
```

```
What's the most expensive product in the store?
```

```
List all products under $100
```

### Order Status
```
What orders are currently pending?
```

```
Show me all delivered orders
```

---

## Multi-Module Queries (2-3 modules)

### User + Orders
```
What has Alice Johnson ordered in the past?
```

```
Show me Bob Smith's order history and current shipment status
```

```
Which user has spent the most money?
```

### Products + Reviews
```
What are the reviews for the iPhone 15 Pro?
```

```
Show me the highest rated products
```

```
Which products have no reviews yet?
```

### Orders + Payments + Shipping
```
What's the status of order ord_003? Include payment and shipping details.
```

```
Are there any orders with pending payments?
```

```
List all shipments that are currently in transit
```

---

## Complex Multi-Module Scenarios (4+ modules)

### Customer Service Scenario
```
Carol White has a support ticket about her delayed order. Look up her ticket, check her order status, and give me a full summary of the situation including payment status and any shipment information.
```

### Customer 360 View
```
Give me a complete profile of Alice Johnson - her contact info, addresses, order history, reviews she's written, wishlist items, and any support tickets.
```

### Inventory & Sales Analysis
```
I need a report on the Electronics category - list all products, their current inventory levels, any recent orders containing these items, and customer reviews.
```

### Support Escalation
```
Emma Davis wants a refund for a sofa she purchased. Look up her support ticket, find the original order, check the payment details, and tell me what needs to happen to process this refund.
```

### Shopping Assistant
```
David Brown has items in his cart. Check what's in his cart, see if any coupons would apply, and complete the checkout using his saved address with Visa payment.
```

### Re-order Flow
```
Alice loved her iPhone 15 Pro. She wants to buy another one as a gift. Use her existing address and process a new order with PayPal payment.
```

---

## Long-Running Complex Tasks

### Full E-Commerce Flow (New Customer)
```
Create a new customer named John Wilson with email john.wilson@email.com and phone +1-555-9999. Add a shipping address: 100 Main Street, Chicago, IL 60601. Then add a MacBook Pro and an Ergonomic Chair to his cart, apply the SUMMER20 coupon, and complete checkout with Mastercard payment. Finally, create a shipment with UPS.
```

### Order Investigation
```
There's an issue with order ord_004. I need you to:
1. Get the full order details
2. Check the payment status
3. See if there's a shipment created
4. Look up any support tickets related to this order
5. Get the customer's contact information
6. Summarize the situation and recommend next steps
```

### Bulk Operations
```
I need to check on all our pending and processing orders. For each one:
1. Get the order details
2. Check if payment is complete
3. Check shipment status
4. List any associated support tickets
Give me a summary table of findings.
```

### Product Launch Preparation
```
We're launching a new product: "AirPods Pro 3" priced at $249.99 in the Electronics/Smartphones category with SKU "APPL-APP3-STD". Create the product, set inventory to 500 units, and then create a promotional coupon "AIRPODS25" for 25% off with minimum order $200 valid until end of 2025.
```

### Customer Retention Analysis
```
Find all customers who have made purchases, check if they have items in their wishlist, and see if any of those wishlist items are currently on sale or have available coupons. Recommend personalized outreach for each customer.
```

### Support Queue Triage
```
Review all open support tickets. For each ticket:
1. Get the ticket details
2. Look up the customer who filed it
3. Check their recent orders
4. Categorize by urgency and recommend resolution steps
```

---

## Edge Cases & Error Handling

### Invalid References
```
Get the order details for order ord_999
```

```
What's in user_unknown's cart?
```

### Empty Results
```
Show me all orders from user_emma (she has no orders, just a cart)
```

```
List support tickets for user_alice (she has none)
```

### Cross-Module Validation
```
Create an order for user_bob with product prod_invalid
```

---

## Conversational Multi-Turn Examples

### Turn 1
```
Who is our customer in Austin, Texas?
```
### Turn 2
```
What has she ordered?
```
### Turn 3
```
Is there any problem with her order?
```
### Turn 4
```
Escalate her support ticket to high priority and add a note that we're expediting shipping
```

---

### Turn 1
```
Show me the standing desk product
```
### Turn 2
```
Who has reviewed it?
```
### Turn 3
```
Add it to Emma's cart
```
### Turn 4
```
Actually, add the ergonomic chair too and checkout with her saved address
```

---

## Performance Test Prompts

### Broad Discovery
```
What capabilities does this API have? List all available modules and summarize what each one does.
```

### Deep Module Exploration
```
I want to understand everything about the order management system. List all order-related tools, explain what each does, and show me the parameters for creating and updating orders.
```

### Cross-Cutting Query
```
Give me a complete business snapshot: total users, total products, pending orders, open support tickets, and revenue from completed orders.
```
