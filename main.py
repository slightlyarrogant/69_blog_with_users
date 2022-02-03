from flask import Flask, render_template, redirect, url_for, flash
import os
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, UserForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
from flask import g, request, redirect, url_for, abort
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import ForeignKey

Base = declarative_base()


# checks user id and if not equal to 1 does not allow access
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
ckeditor = CKEditor(app)
Bootstrap(app)

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# login manager init
login_manager = LoginManager()
login_manager.init_app(app)

# initialize gravatar
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

    # This will act like a List of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    posts = relationship("BlogPost", back_populates='author')
    comments = relationship("Comments", back_populates='comment_author')



class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    # Create Foreign Key, "users.id" the users refers to the table name of User.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # Create reference to the User object, the "posts" refers to the posts property in the User class.
    author = relationship("User", back_populates="posts")

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comments", back_populates='parent_post')


class Comments(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    comment_text = db.Column(db.String(250), nullable=False)

    # child relationship with parent table User
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates='comments')
    # child relationship with parent table BlogPost
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    parent_post = relationship("BlogPost", back_populates='comments')


db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    print(f"logged in:   {current_user}  {current_user.is_authenticated}")
    return render_template("index.html", all_posts=posts, current_user=current_user)


@app.route('/register', methods=['POST', 'GET'])
def register():
    new_user_form = UserForm()
    if new_user_form.validate_on_submit():
        if not(User.query.filter_by(email=new_user_form.email.data).first()):
            new_user = User(
                name=new_user_form.user_name.data,
                email=new_user_form.email.data,
                password=generate_password_hash(new_user_form.password.data,
                                                method='pbkdf2:sha256:10', salt_length=8),
            )
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('get_all_posts'))
        else:
            flash("This email address is already used!")
    return render_template("register.html", form=new_user_form, current_user=current_user)


@app.route('/login', methods=['POST', 'GET'])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        email = login_form.email.data
        password = login_form.password.data
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("Email not registered / user does not exists.")
        elif not(check_password_hash(user.password, password)):
            flash("Wrong password! Please try again.")
        else:
            login_user(user)
            return redirect(url_for('get_all_posts'))
    return render_template("login.html", form=login_form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=['POST', 'GET'])
@admin_required
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to log in in order to comment!")
            return redirect(url_for('login'))
        current_comment = Comments(
            comment_text=comment_form.comment_text.data,
            post_id=post_id,
            author_id=current_user.get_id(),
        )
        db.session.add(current_comment)
        db.session.commit()
    return render_template("post.html", post=requested_post, current_user=current_user, form=comment_form)


@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user)


@app.route("/contact")
def contact():
    return render_template("contact.html", current_user=current_user)


@app.route("/new-post", methods=['POST', 'GET'])
@admin_required
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author_id=current_user.get_id(),
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, current_user=current_user)


@login_required
@app.route("/edit-post/<int:post_id>", methods=['POST', 'GET'])
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author_id = current_user.get_id()
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, current_user=current_user)


@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    # app.run(host='0.0.0.0', port=5000)
    app.run(debug=True)
