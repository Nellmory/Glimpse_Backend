from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import datetime
import os
import jwt
import bcrypt

DATABASE_URL = "sqlite:///glimpse.db"

engine = create_engine(DATABASE_URL, echo=True)

app = Flask(__name__)
CORS(app)

Base = declarative_base()

SECRET_KEY = os.environ.get("SECRET_KEY", "vsu_glimpse_nelly")


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)  # Храним хэш пароля
    email = Column(String(100), unique=True, nullable=False)
    profile_pic = Column(String(255), nullable=True)  # Путь к файлу изображения
    status = Column(String(100), default="")

    posts = relationship("Post", back_populates="user")
    comments = relationship("Comment", back_populates="user")
    likes = relationship("Like", back_populates="user")

    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}')>"


class Post(Base):
    __tablename__ = "posts"

    post_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    image_path = Column(String(255), nullable=False)
    caption = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post")
    likes = relationship("Like", back_populates="post")

    def __repr__(self):
        return f"<Post(post_id={self.post_id}, caption='{self.caption}')>"


class Friendship(Base):
    __tablename__ = "friendships"

    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    friend_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)

    __table_args__ = (
        UniqueConstraint('user_id', 'friend_id', name='unique_friendship'),
    )

    user = relationship("User", foreign_keys=[user_id])
    friend = relationship("User", foreign_keys=[friend_id])


class Comment(Base):
    __tablename__ = "comments"

    comment_id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.post_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    post = relationship("Post", back_populates="comments")
    user = relationship("User", back_populates="comments")

    def __repr__(self):
        return f"<Comment(comment_id={self.comment_id}, text='{self.text}')>"


class Like(Base):
    __tablename__ = "likes"

    post_id = Column(Integer, ForeignKey("posts.post_id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)

    post = relationship("Post", back_populates="likes")
    user = relationship("User", back_populates="likes")


Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()


def check_password(password, hashed_password):
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/registry', methods=['POST'])
def registry():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    username = data.get('username')

    if not email or not password or not username:
        return jsonify({'message': 'Missing required fields'}), 400

    # Validate email (basic)
    if "@" not in email:
        return jsonify({'message': 'Invalid email format'}), 400

    session = Session()
    existing_user = session.query(User).filter(User.email == email).first()
    if existing_user:
        session.close()
        return jsonify({'message': 'Email already registered'}), 409  # Conflict

    hashed_password = hash_password(password)
    new_user = User(username=username, email=email, password=hashed_password)
    session.add(new_user)
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        return jsonify({'message': 'Database error: ' + str(e)}), 500
    finally:
        session.close()

    return jsonify({'message': 'User registered successfully'}), 201


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'message': 'Missing email or password'}), 400

    # Валидация email
    if "@" not in email:
        return jsonify({'message': 'Invalid email format'}), 400

    Session = sessionmaker(bind=engine)
    session = Session()

    user = session.query(User).filter(User.email == email).first()

    if user is None:
        session.close()
        return jsonify({'message': 'Invalid credentials'}), 401

    hashed_password = hash_password(password)
    if user.password != hashed_password:
        session.close()
        return jsonify({'message': 'Invalid credentials'}), 401

    # Создание JWT
    payload = {
        'user_id': user.user_id,
        'username': user.username,
        'email': user.email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)  # Срок действия: 1 час
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

    session.close()
    return jsonify({'token': token}), 200


from generation import generation, hash_password

if __name__ == "__main__":
    with Session(bind=engine) as session:
        generation(session)
        app.run(debug=True, host='0.0.0.0', port=5000)
