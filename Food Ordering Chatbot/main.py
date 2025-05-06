# Author: Dhaval Patel. Codebasics YouTube Channel

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import db_helper
import generic_helper

app = FastAPI()

inprogress_orders = {}

@app.post("/")
async def handle_request(request: Request):
    # Retrieve the JSON data from the request
    payload = await request.json()

    # Extract the necessary information from the payload
    intent = payload['queryResult']['intent']['displayName']
    parameters = payload['queryResult']['parameters']
    session_id = payload['session']  # Extracting the session_id

    intent_handler_dict = {
        'order.add - context: ongoing-order': add_to_order,
        'order.remove - context: ongoing-order': remove_from_order,
        'order.complete - context: ongoing-order': complete_order,
        'track.order - context: ongoing-tracking': track_order
    }

    if intent in intent_handler_dict:
        return intent_handler_dict[intent](parameters, session_id)
    else:
        return JSONResponse(content={"fulfillmentText": "Sorry, I didn't understand that request."})


def add_to_order(parameters: dict, session_id: str):
    food_items = parameters["food-item"]
    quantities = parameters["number"]

    if len(food_items) != len(quantities):
        fulfillment_text = "Sorry, I didn't understand. Can you please specify food items and quantities clearly?"
    else:
        new_food_dict = dict(zip(food_items, quantities))

        if session_id not in inprogress_orders:
            inprogress_orders[session_id] = {}

        # Update the ongoing order
        inprogress_orders[session_id].update(new_food_dict)

    order_str = generic_helper.get_str_from_food_dict(inprogress_orders[session_id])
    fulfillment_text = f"So far you have: {order_str}. Do you need anything else?"

    return JSONResponse(content={"fulfillmentText": fulfillment_text})


def save_to_db(order: dict):
    next_order_id = db_helper.get_next_order_id()

    # Insert individual items along with quantity in orders table
    for food_item, quantity in order.items():
        rcode = db_helper.insert_order_item(food_item, quantity, next_order_id)

        if rcode == -1:
            return -1

    # Now insert order tracking status
    db_helper.insert_order_tracking(next_order_id, "in progress")

    return next_order_id


def complete_order(parameters: dict, session_id: str):
    if session_id not in inprogress_orders:
        fulfillment_text = "I'm having trouble finding your order. Sorry! Can you place a new order please?"
    else:
        order = inprogress_orders[session_id]
        order_id = save_to_db(order)

        if order_id == -1:
            fulfillment_text = "Sorry, I couldn't process your order due to a backend error. Please place a new order again."
        else:
            # Get the total price of the order
            order_total = db_helper.get_total_order_price(order_id)
            fulfillment_text = f"Awesome! We have placed your order. Here is your order id # {order_id}. Your order total is {order_total} which you can pay at the time of delivery!"

        # Delete the session data after order is complete
        del inprogress_orders[session_id]

    return JSONResponse(content={"fulfillmentText": fulfillment_text})



def remove_from_order(parameters: dict, session_id: str):
    if session_id not in inprogress_orders:
        return JSONResponse(content={"fulfillmentText": "I'm having trouble finding your order. Sorry! Can you place a new order please?"})

    food_items = parameters["food-item"]
    current_order = inprogress_orders[session_id]

    removed_items = []
    no_such_items = []

    for item in food_items:
        if item not in current_order:
            no_such_items.append(item)
        else:
            removed_items.append(item)
            del current_order[item]

    fulfillment_text = ""
    if len(removed_items) > 0:
        fulfillment_text += f"Removed {','.join(removed_items)} from your order! "
    if len(no_such_items) > 0:
        fulfillment_text += f"Your current order does not have {','.join(no_such_items)}! "
    if len(current_order.keys()) == 0:
        fulfillment_text += "Your order is empty!"
    else:
        order_str = generic_helper.get_str_from_food_dict(current_order)
        fulfillment_text += f"Here is what is left in your order: {order_str}"

    return JSONResponse(content={"fulfillmentText": fulfillment_text})



def track_order(parameters: dict, session_id: str):
    try:
        order_id = int(parameters['order_id'])
    except (KeyError, ValueError, TypeError):
        return JSONResponse(content={
            "fulfillmentText": "I couldn't understand the order ID. Please provide a valid numeric order ID."
        })

    order_status = db_helper.get_order_status(order_id)

    if order_status:
        fulfillment_text = f"The order status for order ID #{order_id} is: {order_status}."
    else:
        fulfillment_text = f"No order found with order ID #{order_id}."

    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })
