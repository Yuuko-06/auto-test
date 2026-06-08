"""
Demo API Mock Server — 真实内存存储 + 完整业务校验
启动: python main.py
"""
import time
import uuid
from copy import deepcopy
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="Demo API", version="1.0.0")

# ========== 内存数据库 ==========
_users: dict[int, dict] = {}
_products: dict[str, dict] = {}
_orders: dict[str, dict] = {}
_next_user_id = 1


def _uid():
    return str(uuid.uuid4())[:8]


# ========== 种子数据 ==========
for _ in range(3):
    uid = _next_user_id
    _next_user_id += 1
    _users[uid] = {
        "id": uid, "username": f"user{uid}",
        "email": f"user{uid}@example.com",
        "phone": f"1380000{uid:04d}",
        "createdAt": "2026-06-01T10:00:00Z",
    }

for i in range(3):
    pid = f"PROD-{_uid()}"
    _products[pid] = {
        "id": pid, "name": f"商品{i+1}",
        "price": round(9.9 + i * 30, 2),
        "category": ["电子产品", "图书", "食品"][i],
        "stock": (i + 1) * 50,
    }


# ========== 用户管理 ==========

@app.get("/users")
def list_users(page: int = 1, limit: int = 20):
    if page < 1 or limit < 1:
        raise HTTPException(400, "page 和 limit 必须为正整数")
    all_users = list(_users.values())
    start = (page - 1) * limit
    return all_users[start : start + limit]


@app.get("/users/{user_id}")
def get_user(user_id: int):
    if user_id not in _users:
        raise HTTPException(404, "用户不存在")
    return _users[user_id]


@app.post("/users", status_code=201)
def create_user(body: dict):
    username = (body.get("username") or "").strip()
    email = (body.get("email") or "").strip()
    password = body.get("password", "")
    phone = body.get("phone", "")

    # 校验必填
    if not username or not email or not password:
        raise HTTPException(400, "username, email, password 为必填字段")

    # 校验用户名长度
    if len(username) < 3 or len(username) > 20:
        raise HTTPException(400, "用户名长度需在 3-20 之间")

    # 校验密码长度
    if len(password) < 6:
        raise HTTPException(400, "密码长度不能少于 6 位")

    # 校验邮箱格式
    if "@" not in email:
        raise HTTPException(400, "邮箱格式不正确")

    # 检查用户名唯一
    for u in _users.values():
        if u["username"] == username:
            raise HTTPException(409, "用户名已存在")

    global _next_user_id
    uid = _next_user_id
    _next_user_id += 1
    user = {
        "id": uid,
        "username": username,
        "email": email,
        "phone": phone,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _users[uid] = user
    return user


@app.put("/users/{user_id}")
def update_user(user_id: int, body: dict):
    if user_id not in _users:
        raise HTTPException(404, "用户不存在")

    user = _users[user_id]
    email = body.get("email")
    phone = body.get("phone")

    if email is not None:
        if not email.strip() or "@" not in email:
            raise HTTPException(400, "邮箱格式不正确")
        user["email"] = email.strip()
    if phone is not None:
        user["phone"] = phone.strip()

    _users[user_id] = user
    return user


@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int):
    if user_id not in _users:
        raise HTTPException(404, "用户不存在")
    del _users[user_id]


# ========== 商品管理 ==========

@app.get("/products")
def list_products(category: str = None, keyword: str = None):
    result = list(_products.values())
    if category:
        result = [p for p in result if p["category"] == category]
    if keyword:
        kw = keyword.lower()
        result = [p for p in result if kw in p["name"].lower()]
    return result


@app.get("/products/{product_id}")
def get_product(product_id: str):
    if product_id not in _products:
        raise HTTPException(404, "商品不存在")
    return _products[product_id]


@app.post("/products", status_code=201)
def create_product(body: dict):
    name = (body.get("name") or "").strip()
    price = body.get("price")

    if not name:
        raise HTTPException(400, "商品名称不能为空")
    if price is None:
        raise HTTPException(400, "价格为必填项")
    if not isinstance(price, (int, float)) or price < 0.01:
        raise HTTPException(400, "价格必须 >= 0.01")

    category = body.get("category", "")
    stock = body.get("stock", 0)
    if not isinstance(stock, int) or stock < 0:
        raise HTTPException(400, "库存不能为负数")

    pid = f"PROD-{_uid()}"
    product = {
        "id": pid,
        "name": name,
        "price": round(float(price), 2),
        "category": category,
        "stock": stock,
    }
    _products[pid] = product
    return product


@app.patch("/products/{product_id}")
def patch_product(product_id: str, body: dict):
    if product_id not in _products:
        raise HTTPException(404, "商品不存在")

    product = _products[product_id]
    if "price" in body:
        price = body["price"]
        if not isinstance(price, (int, float)) or price <= 0:
            raise HTTPException(400, "价格必须 > 0")
        product["price"] = round(float(price), 2)
    if "stock" in body:
        stock = body["stock"]
        if not isinstance(stock, int):
            raise HTTPException(400, "库存必须为整数")
        new_val = product["stock"] + stock
        if new_val < 0:
            raise HTTPException(400, "库存不足，当前库存为 {}".format(product["stock"]))
        product["stock"] = new_val

    _products[product_id] = product
    return product


# ========== 订单管理 ==========

VALID_ORDER_STATUS = {"pending", "paid", "shipped", "completed", "cancelled"}


@app.get("/orders")
def list_orders(status: str = None, userId: int = None):
    result = list(_orders.values())
    if status:
        if status not in VALID_ORDER_STATUS:
            raise HTTPException(400, f"无效的订单状态: {status}")
        result = [o for o in result if o["status"] == status]
    if userId is not None:
        result = [o for o in result if o["userId"] == userId]
    return result


@app.post("/orders", status_code=201)
def create_order(body: dict):
    user_id = body.get("userId")
    items = body.get("items", [])
    remark = body.get("remark", "")

    # 参数校验
    if not user_id or not isinstance(user_id, int):
        raise HTTPException(422, "userId 为必填且为整数")
    if user_id not in _users:
        raise HTTPException(422, f"用户 {user_id} 不存在")
    if not items or not isinstance(items, list):
        raise HTTPException(422, "items 不能为空")
    for i, item in enumerate(items):
        pid = item.get("productId")
        qty = item.get("quantity", 0)
        if not pid:
            raise HTTPException(422, f"items[{i}].productId 不能为空")
        if not isinstance(qty, int) or qty < 1:
            raise HTTPException(422, f"items[{i}].quantity 必须 >= 1")

    # 检查库存
    for item in items:
        pid = item["productId"]
        qty = item["quantity"]
        if pid not in _products:
            raise HTTPException(422, f"商品 {pid} 不存在")
        if _products[pid]["stock"] < qty:
            raise HTTPException(400, f"商品 {pid} 库存不足: 需要 {qty}, 库存 {_products[pid]['stock']}")

    # 扣减库存
    for item in items:
        pid = item["productId"]
        _products[pid]["stock"] -= item["quantity"]

    oid = f"ORD-{_uid()}"
    order = {
        "id": oid,
        "userId": user_id,
        "items": [{"productId": it["productId"], "quantity": it["quantity"]} for it in items],
        "status": "pending",
        "remark": remark,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _orders[oid] = order
    return order


@app.post("/orders/{order_id}/cancel")
def cancel_order(order_id: str):
    if order_id not in _orders:
        raise HTTPException(404, "订单不存在")

    order = _orders[order_id]
    if order["status"] != "pending":
        raise HTTPException(400, f"订单状态为 '{order['status']}'，不允许取消，仅 pending 状态可取消")

    # 归还库存
    for item in order["items"]:
        pid = item["productId"]
        if pid in _products:
            _products[pid]["stock"] += item["quantity"]

    order["status"] = "cancelled"
    _orders[order_id] = order
    return order


# ========== 健康检查 ==========

@app.get("/health")
def health():
    return {"status": "ok", "service": "mock-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8084)
