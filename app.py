from itertools import product

import requests
from flask import Flask, render_template, request, make_response, redirect, session, url_for, flash
# Import the actual products list from your data file
from data import products

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = "8218708595:AAH2GIYkr7Q4OiC72CnYqn8-qcgB5g8Dz0o"
TELEGRAM_CHAT_ID = "-1003855315911"

@app.route('/')
def home():
    # Pass the products list directly into the template
    return render_template('page/home.html', product_list=products)

@app.route('/products')
def view_products(): # Renamed function to avoid conflict with the variable 'products'
    return render_template('page/product.html', products=products)


@app.route('/cart')
def cart():
    # 1. Fetch the raw cookie string (e.g., "3,3,3,3,3,3,3,3,3,3,2")
    cart_cookie = request.cookies.get('shopping_cart', '')
    cart_ids = [int(item_id) for item_id in cart_cookie.split(',') if item_id]

    # 2. Use a temporary dictionary to count the quantities of each ID
    id_counts = {}
    for item_id in cart_ids:
        id_counts[item_id] = id_counts.get(item_id, 0) + 1

    # 3. Build your custom cart_list containing explicit dictionary objects
    cart_list = []
    for item_id, qty in id_counts.items():
        # Find the product details from your master list
        matched_item = next((p for p in products if p['id'] == item_id), None)

        if matched_item:
            # Constructing the exact dictionary structure you requested
            cart_list.append({
                "id": matched_item["id"],
                "title": matched_item["title"],
                "price": matched_item["price"],
                "image": matched_item["image"],
                "category": matched_item["category"],
                "qty": qty,  # <-- Your dynamic qty
                "row_total": matched_item["price"] * qty  # <-- Price * qty
            })

    # Calculate the grand total of the whole cart
    grand_total = sum(item['row_total'] for item in cart_list)

    # Pass your clean cart_list down to the template
    return render_template('page/view-cart.html', cart=cart_list, total=grand_total)


@app.route('/product')
def product_detail():
    product_id = request.args.get('id', type=int)

    if not product_id:
        return "Product ID is required", 400

    product = next((p for p in products if p['id'] == product_id), None)

    if product is None:
        return "Product Not Found", 404

    # 1. Grab existing cart cookie (returns an empty string if cookie doesn't exist)
    existing_cart = request.cookies.get('shopping_cart', '')

    # 2. Look for the 'add=True' flag from our HTML link
    is_adding = request.args.get('add', type=bool, default=False)

    # Prepare the initial response object
    response = make_response(render_template('page/product_detail.html', product=product))

    if is_adding:
        # Build a comma-separated string of IDs (e.g., "1,4,2")
        if existing_cart:
            updated_cart = f"{existing_cart},{product_id}"
        else:
            updated_cart = str(product_id)

        # 3. Save the string back to the browser cookies (valid for 30 days)
        response.set_cookie('shopping_cart', updated_cart, max_age=2592000)

    return response


@app.route('/cart/add')
def add_to_cart():
    product_id = request.args.get('id', type=int)
    if not product_id:
        return "Product ID is required", 400

    # 1. Grab the existing cart cookie string
    existing_cart = request.cookies.get('shopping_cart', '')

    # 2. Append the new product ID to the string
    if existing_cart:
        updated_cart = f"{existing_cart},{product_id}"
    else:
        updated_cart = str(product_id)

    # 3. Create a redirect pointing straight to your /cart route
    response = make_response(redirect('/cart'))

    # 4. Save the updated string back into the browser cookie storage
    response.set_cookie('shopping_cart', updated_cart, max_age=2592000)

    return response


@app.route('/cart/update', methods=['POST'])
def update_cart():
    product_id = request.form.get('product_id', type=int)
    action = request.form.get('action')  # 'increase' or 'decrease'

    if not product_id:
        return redirect('/cart')

    # Read the existing flat cookie string sequence
    cart_cookie = request.cookies.get('shopping_cart', '')
    cart_ids = [int(item_id) for item_id in cart_cookie.split(',') if item_id]

    if action == 'increase':
        # Simply append another instance of this ID to the tracking array
        cart_ids.append(product_id)

    elif action == 'decrease':
        # Remove exactly one instance of this item ID from the array list if present
        if product_id in cart_ids:
            cart_ids.remove(product_id)

    # Reassemble the comma-separated string from the updated array list
    updated_cookie_str = ",".join(map(str, cart_ids))

    # Save the updated value string structure directly back into the browser cookie storage
    response = make_response(redirect('/cart'))
    if updated_cookie_str:
        response.set_cookie('shopping_cart', updated_cookie_str, max_age=2592000)
    else:
        # If the cart is now completely empty, drop the cookie key entirely
        response.delete_cookie('shopping_cart')

    return response


@app.route('/checkout', methods=['POST'])
def checkout():
    # 1. Fetch the data straight from cookies (just like the /cart route does)
    cart_cookie = request.cookies.get('shopping_cart', '')

    if not cart_cookie:
        flash("Your cart is empty!", "warning")
        return redirect('/products')

    cart_ids = [int(item_id) for item_id in cart_cookie.split(',') if item_id]

    # 2. Count quantities of each product ID
    id_counts = {}
    for item_id in cart_ids:
        id_counts[item_id] = id_counts.get(item_id, 0) + 1

    # 3. Build the cart list using your data list to format the Telegram notification
    cart_list = []
    grand_total = 0.0

    for item_id, qty in id_counts.items():
        matched_item = next((p for p in products if p['id'] == item_id), None)
        if matched_item:
            row_total = matched_item["price"] * qty
            grand_total += row_total
            cart_list.append({
                "title": matched_item["title"],
                "category": matched_item["category"],
                "price": matched_item["price"],
                "qty": qty,
                "row_total": row_total
            })

    if not cart_list:
        flash("Your cart items are invalid!", "warning")
        return redirect('/products')

    # 4. Format a clean, highly readable message for your Telegram chat
    message = "🛍️ **NEW ORDER RECEIVED** 🛍️\n\n"
    for item in cart_list:
        message += f"📦 *Product:* {item['title']}\n"
        message += f"🏷️ *Category:* {item['category']}\n"
        message += f"🔢 *Quantity:* {item['qty']} x ${item['price']:.2f}\n"
        message += f"💵 *Subtotal:* ${item['row_total']:.2f}\n"
        message += "-------------------------\n"

    message += f"🎯 **TOTAL PAID: ${grand_total:.2f}**"

    # 5. Send the payload to Telegram API
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        api_response = requests.post(telegram_url, json=payload)
        if api_response.status_code == 200:
            # 6. Success! Clear the shopping cart cookie from the user's browser
            # We redirect to a success state or home, clearing the cookie on the way out
            response = make_response(redirect('/payment_success'))
            response.delete_cookie('shopping_cart')
            return response
        else:
            return f"Telegram API Error: {api_response.text}", 400

    except Exception as e:
        return f"Failed to send order notification: {str(e)}", 500


@app.route('/payment_success')
def payment_success():
    return render_template('page/susccess_payment.html')

@app.route('/about')
def about():
    return render_template('page/about.html')

@app.route('/contact')
def contact():
    return render_template('page/contact.html')

@app.route('/register')
def register():

    return render_template('page/register.html')

@app.route('/login')
def login():

    return render_template('page/login.html')

@app.route('/settings')
def settings():

    return render_template('page/setting.html')

if __name__ == '__main__':
    app.run(debug=True)