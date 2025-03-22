from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from flask import Flask, render_template, request, jsonify
import datetime

DATABASE_URL = "sqlite:///glimpse.db"

engine = create_engine(DATABASE_URL, echo=True)

app = Flask(__name__)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)  # Храним хэш пароля
    email = Column(String(100), unique=True, nullable=False)
    profile_pic = Column(String(255), nullable=True)  # Путь к файлу изображения

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

    user = relationship("User", foreign_keys=[user_id])  # type: ignore
    friend = relationship("User", foreign_keys=[friend_id])  # type: ignore


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


from generation import generation

if __name__ == "__main__":
    with Session(bind=engine) as session:
        #generation(session)
        app.run(debug=True, host='0.0.0.0', port=5000)
