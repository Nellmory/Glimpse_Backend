import hashlib
from functools import wraps

from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import datetime
import os
import jwt
import uuid
from PIL import Image

DATABASE_URL = "sqlite:///glimpse.db"

engine = create_engine(DATABASE_URL, echo=True)

app = Flask(__name__)
CORS(app)

Base = declarative_base()

SECRET_KEY = os.environ.get("SECRET_KEY", "vsu_glimpse_nelly")

IMAGE_STORAGE_PATH = 'C:/Users/agapo/PycharmProjects/Glimpse/images'
BASE_URL = 'http://192.168.0.102:5000'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}


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
    timestamp = Column(DateTime, default=datetime.datetime.utcnow())

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
    timestamp = Column(DateTime, default=datetime.datetime.utcnow())

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


# Функция для проверки JWT
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            session = Session()
            current_user = session.query(User).filter_by(user_id=data['user_id']).first()
            if current_user:
                kwargs['current_user'] = current_user
            else:
                return jsonify({'message': 'Invalid token: User not found'}), 401
            session.close()
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token!'}), 401
        return f(*args, **kwargs)

    return decorated


@app.route('/api/user', methods=['GET'])
@token_required
def get_user(current_user):
    """Возвращает информацию о пользователе на основе JWT."""
    user_data = {
        'user_id': current_user.user_id,
        'username': current_user.username,
        'email': current_user.email,
        'profile_pic': current_user.profile_pic,
        'status': current_user.status,
    }
    return jsonify(user_data), 200


@app.route('/api/users/<int:user_id>/status', methods=['PUT'])
def update_user_status_route(user_id):
    """Обновляет статус пользователя"""
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


@app.route('/api/friends/<int:user_id>', methods=['GET'])
@token_required
def get_friends(current_user, user_id):
    """Возвращает список друзей пользователя (только взаимные)."""
    session = Session()
    try:
        # Находим всех, кто добавил user_id в друзья.
        friendships1 = session.query(Friendship).filter(Friendship.friend_id == user_id).all()

        # Создаем список потенциальных друзей (тех, кто добавил user_id)
        potential_friend_ids = [friendship.user_id for friendship in friendships1]

        # Теперь, проверяем, добавил ли user_id этих людей в друзья.
        mutual_friend_ids = []
        for potential_friend_id in potential_friend_ids:
            friendship = session.query(Friendship).filter(
                Friendship.user_id == user_id,
                Friendship.friend_id == potential_friend_id
            ).first()
            if friendship:  # Если такая запись существует, значит, дружба взаимная.
                mutual_friend_ids.append(potential_friend_id)

        # Получаем информацию о взаимных друзьях.
        friends = session.query(User).filter(User.user_id.in_(mutual_friend_ids)).all()

        friends_list = []
        for friend in friends:
            friends_list.append({
                'user_id': friend.user_id,
                'username': friend.username,
                'email': friend.email,
                'profile_pic': friend.profile_pic,
                'status': friend.status,
            })

        return jsonify(friends_list), 200

    except Exception as e:
        print(f"Ошибка при получении списка друзей: {e}")
        return jsonify({'message': 'Failed to get friends'}), 500
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


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/upload/<int:user_id>', methods=['POST'])
def upload_image(user_id):
    if 'image' not in request.files:
        return jsonify({'error': 'No image part'}), 400

    image = request.files['image']

    if image.filename == '':
        return jsonify({'error': 'No selected image'}), 400

    if image and allowed_file(image.filename):
        try:
            # Генерируем уникальное имя файла
            file_extension = os.path.splitext(image.filename)[1].lower()
            filename = str(uuid.uuid4()) + file_extension

            # Создаем путь с годом/месяцем/днем/user_id
            now = datetime.datetime.now()
            sub_directory = os.path.join(str(now.year), str(now.month), str(now.day), str(user_id))
            save_directory = os.path.join(IMAGE_STORAGE_PATH, sub_directory)

            # Создаем директорию, если ее нет
            os.makedirs(save_directory, exist_ok=True)

            file_path = os.path.join(save_directory, filename)

            # Сохраняем изображение
            img = Image.open(image)
            img.save(file_path)

            # Формируем URL изображения
            image_url = f'{BASE_URL}/images/{sub_directory}/{filename}'  # Абсолютный URL

            return jsonify({'image_url': image_url}), 200

        except Exception as e:
            return jsonify({'error': f'Error saving image: {str(e)}'}), 500

    return jsonify({'error': 'Invalid file format'}), 400


@app.route('/api/images/<path:image_path>')
def serve_image(image_path):
    #  `/images/2024/01/unique_image.jpg`
    try:
        return send_from_directory(IMAGE_STORAGE_PATH, image_path)
    except FileNotFoundError:
        return jsonify({'error': 'Image not found'}), 404


from generation import generation, hash_password

if __name__ == "__main__":
    with Session(bind=engine) as session:
        generation(session)
        app.run(debug=True, host='0.0.0.0', port=5000)
