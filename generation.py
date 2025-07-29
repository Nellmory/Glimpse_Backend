from __main__ import User, Like, Comment, Post, Friendship
import hashlib


def hash_password(password):
    """Хэширует пароль с использованием SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def create_user(session, username, password, email, profile_pic=None, status=""):
    """Создает нового пользователя."""
    hashed_password = hash_password(password)
    new_user = User(username=username, password=hashed_password, email=email, profile_pic=profile_pic, status=status)
    session.add(new_user)
    try:
        session.commit()
        return new_user
    except Exception as e:
        session.rollback()  # Откатываем транзакцию в случае ошибки
        print(f"Ошибка при создании пользователя: {e}")
        return None


def update_user_status(session, user_id, new_status):
    """Обновляет статус пользователя."""
    user = session.query(User).get(user_id)
    if user:
        user.status = new_status
        try:
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"Ошибка при обновлении статуса: {e}")
            return False
    else:
        print(f"Пользователь с id {user_id} не найден.")
        return False


def create_post(session, user_id, image_path, caption=None):
    """Создает новый пост."""
    new_post = Post(user_id=user_id, image_path=image_path, caption=caption)
    session.add(new_post)
    try:
        session.commit()
        return new_post
    except Exception as e:
        session.rollback()
        print(f"Ошибка при создании поста: {e}")
        return None


def add_friend(session, user_id, friend_id):
    """Добавляет пользователя в друзья."""
    friendship = Friendship(user_id=user_id, friend_id=friend_id)
    session.add(friendship)
    try:
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Ошибка при добавлении в друзья: {e}")
        return False


def add_comment(session, post_id, user_id, text):
    """Добавляет комментарий к посту."""
    new_comment = Comment(post_id=post_id, user_id=user_id, text=text)
    session.add(new_comment)
    try:
        session.commit()
        return new_comment
    except Exception as e:
        session.rollback()
        print(f"Ошибка при добавлении комментария: {e}")
        return None


def like_post(session, post_id, user_id):
    """Ставит лайк посту."""
    like = Like(post_id=post_id, user_id=user_id)
    session.add(like)
    try:
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Ошибка при лайке поста: {e}")
        return False


def get_posts_for_user(session, user_id):
    """Получает все посты для конкретного пользователя."""
    return session.query(Post).filter(Post.user_id == user_id).order_by(Post.timestamp.desc()).all()


def get_friends_posts(session, user_id):
    """Получает посты всех друзей пользователя."""
    return session.query(Post).join(Friendship, Post.user_id == Friendship.friend_id).filter(
        Friendship.user_id == user_id).order_by(Post.timestamp.desc()).all()


def get_post_comments(session, post_id):
    """Получает все комментарии к определенному посту."""
    return session.query(Comment).filter(Comment.post_id == post_id).order_by(Comment.timestamp).all()


def get_post_likes_count(session, post_id):
    """Получает количество лайков для определенного поста."""
    return session.query(Like).filter(Like.post_id == post_id).count()


def generation(session):
    # Создаем пользователей
    alice = create_user(session, "Alice2025", "password123", "alice@example.com")
    bob = create_user(session, "Bob", "securepass", "bob@example.com")
    nelly = create_user(session, "Nelly", "1234", "agapova.nelli@gmail.com")
    daniel = create_user(session, "Daniel", "12345", "den@gmail.com")
    dasha = create_user(session, "Dar Husan", "123456", "dar@gmail.com")
    Lena = create_user(session, "Lena V", "1234567", "lena@gmail.com")
    charlie = create_user(session, "CharlieXXX", "mysecret", "charlie@example.com")

    if alice and bob and charlie:  # Убеждаемся, что пользователи создались успешно.
        # Обновляем статус пользователя
        update_user_status(session, alice.user_id, "Наслаждаюсь жизнью!")
        update_user_status(session, charlie.user_id, "В отпуске!")

        # Создаем посты
        post1 = create_post(session, nelly.user_id, "2025/5/29/4/img.png", "Моя первая фотография!")
        post2 = create_post(session, bob.user_id, "/path/to/image2.jpg", "Отличный день!")

        if post1 and post2:  # Убеждаемся, что посты создались успешно
            # Добавляем в друзья
            add_friend(session, nelly.user_id, bob.user_id)
            add_friend(session, nelly.user_id, Lena.user_id)
            add_friend(session, nelly.user_id, dasha.user_id)
            add_friend(session, nelly.user_id, charlie.user_id)
            add_friend(session, bob.user_id, nelly.user_id)
            add_friend(session, Lena.user_id, nelly.user_id)
            add_friend(session, dasha.user_id, nelly.user_id)
            add_friend(session, charlie.user_id, nelly.user_id)

            add_friend(session, bob.user_id, alice.user_id)
            add_friend(session, charlie.user_id, alice.user_id)

            # Комментарии
            add_comment(session, post1.post_id, bob.user_id, "Крутая фотка!")
            #add_comment(session, post1.post_id, charlie.user_id, "Согласен!")

            # Лайки
            like_post(session, post1.post_id, bob.user_id)
            #like_post(session, post1.post_id, charlie.user_id)
            like_post(session, post2.post_id, alice.user_id)

            # Получаем посты друзей
            friends_posts = get_friends_posts(session, alice.user_id)
            print("\nПосты друзей Alice:")
            for post in friends_posts:
                print(post)

            # Получаем количество лайков
            likes_count = get_post_likes_count(session, post1.post_id)
            print(f"\nКоличество лайков для поста 1: {likes_count}")

    else:
        print("Не удалось создать пользователей, проверьте ошибки.")
