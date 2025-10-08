#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont

W, H = 1600, 1000
BG = (250, 250, 250)
BOX = (255, 255, 255)
STROKE = (50, 50, 50)
ACCENT = (39, 123, 192)
LINK = (120, 120, 120)

def draw_box(draw: ImageDraw.ImageDraw, xy, title: str, lines, fill=BOX, outline=STROKE):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle([x1, y1, x2, y2], radius=12, fill=fill, outline=outline, width=2)
    try:
        font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
        font_body = ImageFont.truetype("DejaVuSans.ttf", 14)
    except Exception:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()
    draw.text((x1+12, y1+8), title, fill=ACCENT, font=font_title)
    y = y1 + 36
    for line in lines:
        draw.text((x1+12, y), line, fill=(30,30,30), font=font_body)
        y += 18

def arrow(draw: ImageDraw.ImageDraw, p1, p2, color=LINK):
    x1,y1 = p1; x2,y2 = p2
    draw.line([x1,y1,x2,y2], fill=color, width=2)
    # arrow head
    import math
    ang = math.atan2(y2-y1, x2-x1)
    ah = 10
    left = (x2 - ah*math.cos(ang - math.pi/6), y2 - ah*math.sin(ang - math.pi/6))
    right = (x2 - ah*math.cos(ang + math.pi/6), y2 - ah*math.sin(ang + math.pi/6))
    draw.polygon([p2, left, right], fill=color)

def main():
    img = Image.new("RGB", (W,H), BG)
    d = ImageDraw.Draw(img)

    # Main: OrdersTable
    orders_box = (600, 120, 1000, 360)
    draw_box(d, orders_box, "dev-promodeagro-admin-OrdersTable", [
        "PK: id (S)",
        "GSIs:",
        " - userIdIndex: userId",
        " - statusCreatedAtIndex: status, createdAt",
        " - idCreatedAtIndex: id, createdAt",
        " - packerCreatedAtIndex: packer_id, createdAt",
        "Attrs: userId, customerId, status, createdAt, updatedAt, subTotal, finalTotal",
        "       items[], address{}, paymentDetails{}, deliverySlot{}, packed_by, packed_at"
    ])

    # Linked tables and keys
    users_box = (140, 60, 520, 180)
    draw_box(d, users_box, "dev-promodeagro-admin-promodeagroUsers", [
        "PK: id (S)",
        "GSIs: emailIndex, numberIndex",
        "Linked via Orders.userId/customerId -> Users.id"
    ])

    addresses_box = (140, 210, 520, 330)
    draw_box(d, addresses_box, "dev-promodeagro-admin-Addresses", [
        "PK/SK: userId (S), addressId (S)",
        "Linked via Orders.address.{userId,addressId}"
    ])

    products_box = (140, 360, 520, 520)
    draw_box(d, products_box, "dev-promodeagro-admin-productsTable", [
        "PK: id (S) | GSIs: name, groupId, category, subCategory",
        "Linked via Orders.items[].productId -> Products.id"
    ])

    inventory_box = (140, 540, 520, 660)
    draw_box(d, inventory_box, "dev-promodeagro-admin-inventoryTable", [
        "PK: id (S) | GSI: productIdIndex",
        "Linked via Products.id -> Inventory.productId"
    ])

    packers_box = (1060, 80, 1480, 200)
    draw_box(d, packers_box, "dev-promodeagro-admin-PackersTable", [
        "PK: packer_id (S)",
        "GSIs: email-index, status-index, isOnline-index",
        "Linked via Orders.packer_id -> Packers.packer_id"
    ])

    runsheet_box = (1060, 230, 1480, 370)
    draw_box(d, runsheet_box, "dev-promodeagro-admin-runsheetTable", [
        "PK: id (S)",
        "GSIs: riderIndex (riderId), statusCreatedAtIndex",
        "Links Orders by orderId within runsheet payload"
    ])

    slots_box = (1060, 400, 1480, 500)
    draw_box(d, slots_box, "dev-promodeagro-admin-DeliveryTimeSlots", [
        "PK: slotId (S)",
        "Linked via Orders.deliverySlot.id -> TimeSlots.slotId"
    ])

    riders_box = (1060, 530, 1480, 650)
    draw_box(d, riders_box, "dev-promodeagro-rider-ridersTable", [
        "PK: id (S) | GSI: number-index",
        "Linked via Orders.riderId -> Riders.id"
    ])

    # arrows
    def center(box):
        x1,y1,x2,y2 = box
        return ((x1+x2)//2, (y1+y2)//2)

    # Users -> Orders
    arrow(d, (520,120), (600,180))
    # Addresses -> Orders
    arrow(d, (520,270), (600,240))
    # Products -> Orders
    arrow(d, (520,420), (600,300))
    # Inventory -> Products
    arrow(d, (520,600), (520,520))
    # Packers -> Orders
    arrow(d, (1060,140), (1000,180))
    # Runsheet -> Orders (conceptual)
    arrow(d, (1060,300), (1000,260))
    # Slots -> Orders
    arrow(d, (1060,450), (1000,320))
    # Riders -> Orders
    arrow(d, (1060,590), (1000,340))

    # Title
    try:
        font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
    except Exception:
        font_title = ImageFont.load_default()
    d.text((20, 10), "Promodeagro Dev - Orders Domain Relationships (DynamoDB)", fill=(0,0,0), font=font_title)

    img.save("design.png")
    print("Wrote design.png")

if __name__ == "__main__":
    main()


