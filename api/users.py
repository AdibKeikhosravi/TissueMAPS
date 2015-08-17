import json

from flask import request, jsonify

from models import User
from api import api
from db import db


@api.route('/register', methods=['POST'])
def register():
    data = json.loads(request.data)
    password = data.get('password')
    username = data.get('username')
    email = data.get('email')

    u = User(name=username, password=password, email=email)
    db.session.add(u)
    db.session.commit()

    return jsonify({
        'id': u.id,
        'name': username,
        'email': email
    })
