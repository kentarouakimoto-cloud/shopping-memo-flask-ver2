# app.py
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    current_user,
    UserMixin,
)
from werkzeug.security import generate_password_hash, check_password_hash
from markupsafe import Markup, escape

# --- アプリ初期化 ---
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
app.config[
    "SQLALCHEMY_DATABASE_URI"
] = os.environ.get("DATABASE_URL", "sqlite:///app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# --- 拡張機能 ---
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# --- Jinja フィルター: nl2br ---
@app.template_filter("nl2br")
def nl2br_filter(s):
    """改行を <br> に変換して安全に返すフィルター"""
    if s is None:
        return ""
    return Markup("<br>\n".join(escape(s).splitlines()))

# --- モデル ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    memos = db.relationship("Memo", backref="owner", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Memo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


# --- Flask-Login: ユーザーローダー ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- ルート / CRUD --- 
@app.route("/")
@login_required
def index():
    # オプション: ?q=検索 に対応するならここでフィルタする
    memos = (
        Memo.query.filter_by(user_id=current_user.id)
        .order_by(Memo.created_at.desc())
        .all()
    )
    return render_template("index.html", memos=memos)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("ユーザー名とパスワードは必須です。")
            return redirect(url_for("register"))
        if User.query.filter_by(username=username).first():
            flash("そのユーザー名は既に使われています。")
            return redirect(url_for("register"))
        u = User(username=username)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        flash("アカウントを作成しました。ログインしてください。")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("index"))
        flash("ユーザー名またはパスワードが違います。")
        return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("ログアウトしました。")
    return redirect(url_for("login"))


@app.route("/memo/new", methods=["GET", "POST"])
@login_required
def new_memo():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        if not title:
            flash("タイトルは必須です。")
            return redirect(url_for("new_memo"))
        m = Memo(title=title, content=content, user_id=current_user.id)
        db.session.add(m)
        db.session.commit()
        flash("メモを保存しました。")
        return redirect(url_for("index"))
    return render_template("memo_form.html", memo=None)


@app.route("/memo/<int:memo_id>/edit", methods=["GET", "POST"])
@login_required
def edit_memo(memo_id):
    memo = Memo.query.get_or_404(memo_id)
    if memo.user_id != current_user.id:
        flash("その操作はできません。")
        return redirect(url_for("index"))
    if request.method == "POST":
        memo.title = request.form.get("title", "").strip()
        memo.content = request.form.get("content", "").strip()
        db.session.commit()
        flash("メモを更新しました。")
        return redirect(url_for("index"))
    return render_template("memo_form.html", memo=memo)


@app.route("/memo/<int:memo_id>/delete", methods=["POST"])
@login_required
def delete_memo(memo_id):
    memo = Memo.query.get_or_404(memo_id)
    if memo.user_id != current_user.id:
        flash("その操作はできません。")
        return redirect(url_for("index"))
    db.session.delete(memo)
    db.session.commit()
    flash("メモを削除しました。")
    return redirect(url_for("index"))


# --- 補助ルート（テンプレートが memo を参照している場合の互換） ---
@app.route("/memo")
@login_required
def memo_redirect():
    return redirect(url_for("index"))


# --- 起動 ---
if __name__ == "__main__":
    # 初回実行時に DB を作成（簡易）
    with app.app_context():
        db.create_all()
    # Render 等の PaaS は PORT 環境変数を渡すので受け取る
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
