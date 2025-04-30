import hashlib

from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import datetime
import os
import jwt

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

    session = Session()

    user = session.query(User).filter(User.email == email).first()

    if user is None:
        session.close()
        return jsonify({'message': 'Invalid credentials'}), 401

    # Проверка пароля
    if not check_password(password, user.password):
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


def hash_password(password):
    """Хэширует пароль с использованием SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def check_password(password, hashed_password):
    """Проверяет, соответствует ли введенный пароль хешированному."""
    return hash_password(password) == hashed_password


@app.route('/api/users', methods=['POST'])
def create_user_route():
    """Создает нового пользователя (endpoint)."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    profile_pic = data.get('profile_pic')
    status = data.get('status')

    if not username or not password or not email:
        return jsonify({'message': 'Missing required fields'}), 400

    session = Session()
    try:
        hashed_password = hash_password(password)
        new_user = User(username=username, password=hashed_password, email=email, profile_pic=profile_pic,
                        status=status)
        session.add(new_user)
        try:
            session.commit()
        except Exception as e:
            session.rollback()  # Откатываем транзакцию в случае ошибки
            print(f"Ошибка при создании пользователя: {e}")
            new_user = None
        if new_user:
            return jsonify({'user_id': new_user.user_id, 'message': 'User created successfully'}), 201
        else:
            return jsonify({'message': 'Failed to create user'}), 500
    finally:
        session.close()


@app.route('/api/users/<int:user_id>/status', methods=['PUT'])
def update_user_status_route(user_id):
    """Обновляет статус пользователя (endpoint)."""
    data = request.get_json()
    new_status = data.get('status')

    if not new_status:
        return jsonify({'message': 'Missing status field'}), 400

    session = Session()
    try:
        user = session.query(User).get(user_id)
        success = False
        if user:
            user.status = new_status
            try:
                session.commit()
                success = True
            except Exception as e:
                session.rollback()
                print(f"Ошибка при обновлении статуса: {e}")
        else:
            print(f"Пользователь с id {user_id} не найден.")
        if success:
            return jsonify({'message': 'User status updated successfully'}), 200
        else:
            return jsonify({'message': f'User with id {user_id} not found or failed to update'}), 404
    finally:
        session.close()


@app.route('/api/posts', methods=['POST'])
def create_post_route():
    """Создает новый пост (endpoint)."""
    data = request.get_json()
    user_id = data.get('user_id')
    image_path = data.get('image_path')
    caption = data.get('caption')

    if not user_id or not image_path:
        return jsonify({'message': 'Missing required fields'}), 400

    session = Session()
    try:
        new_post = Post(user_id=user_id, image_path=image_path, caption=caption)
        session.add(new_post)
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Ошибка при создании поста: {e}")
            new_post = None
        if new_post:
            return jsonify({'post_id': new_post.post_id, 'message': 'Post created successfully'}), 201
        else:
            return jsonify({'message': 'Failed to create post'}), 500
    finally:
        session.close()


@app.route('/api/friends', methods=['POST'])
def add_friend_route():
    """Добавляет пользователя в друзья (endpoint)."""
    data = request.get_json()
    user_id = data.get('user_id')
    friend_id = data.get('friend_id')

    if not user_id or not friend_id:
        return jsonify({'message': 'Missing required fields'}), 400

    session = Session()
    try:
        success = False
        friendship = Friendship(user_id=user_id, friend_id=friend_id)
        session.add(friendship)
        try:
            session.commit()
            success = True
        except Exception as e:
            session.rollback()
            print(f"Ошибка при добавлении в друзья: {e}")
        if success:
            return jsonify({'message': 'Friend added successfully'}), 200
        else:
            return jsonify({'message': 'Failed to add friend'}), 500
    finally:
        session.close()


@app.route('/api/comments', methods=['POST'])
def add_comment_route():
    """Добавляет комментарий к посту (endpoint)."""
    data = request.get_json()
    post_id = data.get('post_id')
    user_id = data.get('user_id')
    text = data.get('text')

    if not post_id or not user_id or not text:
        return jsonify({'message': 'Missing required fields'}), 400

    session = Session()
    try:
        new_comment = Comment(post_id=post_id, user_id=user_id, text=text)
        session.add(new_comment)
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Ошибка при добавлении комментария: {e}")
            new_comment = None
        if new_comment:
            return jsonify({'comment_id': new_comment.comment_id, 'message': 'Comment added successfully'}), 201
        else:
            return jsonify({'message': 'Failed to add comment'}), 500
    finally:
        session.close()


@app.route('/api/likes', methods=['POST'])
def like_post_route():
    """Ставит лайк посту (endpoint)."""
    data = request.get_json()
    post_id = data.get('post_id')
    user_id = data.get('user_id')

    if not post_id or not user_id:
        return jsonify({'message': 'Missing required fields'}), 400

    session = Session()
    try:
        success = False
        like = Like(post_id=post_id, user_id=user_id)
        session.add(like)
        try:
            session.commit()
            success = True
        except Exception as e:
            session.rollback()
            print(f"Ошибка при лайке поста: {e}")
        if success:
            return jsonify({'message': 'Post liked successfully'}), 200
        else:
            return jsonify({'message': 'Failed to like post'}), 500
    finally:
        session.close()


@app.route('/api/users/<int:user_id>/posts', methods=['GET'])
def get_user_posts_route(user_id):
    """Получает посты пользователя (endpoint)."""
    session = Session()
    try:
        posts = session.query(Post).filter(Post.user_id == user_id).order_by(Post.timestamp.desc()).all()
        post_list = [
            {'post_id': post.post_id, 'user_id': post.user_id, 'image_path': post.image_path, 'caption': post.caption,
             'timestamp': post.timestamp.isoformat()} for post in posts]
        return jsonify(post_list), 200
    finally:
        session.close()


@app.route('/api/friends/<int:user_id>/posts', methods=['GET'])
def get_friends_posts_route(user_id):
    """Получает посты друзей пользователя (endpoint)."""
    session = Session()
    try:
        posts = session.query(Post).join(Friendship, Post.user_id == Friendship.friend_id).filter(
            Friendship.user_id == user_id).order_by(Post.timestamp.desc()).all()
        post_list = [
            {'post_id': post.post_id, 'user_id': post.user_id, 'image_path': post.image_path, 'caption': post.caption,
             'timestamp': post.timestamp.isoformat()} for post in posts]
        return jsonify(post_list), 200
    finally:
        session.close()


@app.route('/api/posts/<int:post_id>/comments', methods=['GET'])
def get_post_comments_route(post_id):
    """Получает комментарии к посту (endpoint)."""
    session = Session()
    try:
        comments = session.query(Comment).filter(Comment.post_id == post_id).order_by(Comment.timestamp).all()
        comment_list = [{'comment_id': comment.comment_id, 'post_id': comment.post_id, 'user_id': comment.user_id,
                         'text': comment.text, 'timestamp': comment.timestamp.isoformat()} for comment in comments]
        return jsonify(comment_list), 200
    finally:
        session.close()


@app.route('/api/posts/<int:post_id>/likes/count', methods=['GET'])
def get_post_likes_count_route(post_id):
    """Получает количество лайков поста (endpoint)."""
    session = Session()
    try:
        likes_count = session.query(Like).filter(Like.post_id == post_id).count()
        return jsonify({'likes_count': likes_count}), 200
    finally:
        session.close()


from generation import generation, hash_password

if __name__ == "__main__":
    with Session(bind=engine) as session:
        generation(session)
        app.run(debug=True, host='0.0.0.0', port=5000)
