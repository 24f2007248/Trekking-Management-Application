from flask import render_template, request, redirect, url_for, session
from models.models import engine, User, StaffProfile
from sqlalchemy.orm import Session

def init_app_routes(app):
    @app.route("/", methods=["GET", "POST"])
    def login():
        if request.method == "POST":

            email = request.form["email"]
            password = request.form["password"]

            with Session(engine) as db:
                user = db.query(User).filter(User.email == email).first()

                if user is None:
                    return render_template("login.html", error="Invalid email")
                if not user.is_active:
                    return render_template("login.html", error="Account not active")
                if user.check_password(password):
                    session['userid'] = user.userid
                    session['name'] = user.name
                    session['role'] = user.role

                    if user.role == "admin":
                        return url_for("admin_dashboard")
                    elif user.role == "staff":
                        staff = db.query(StaffProfile).filter(StaffProfile.userid == user.userid).first()
                        if staff.approval_status != "Approved":
                            session.clear()
                            return render_template("login.html", error="Your account is awaiting admin approval.")
                        return url_for("staff_dashboard")
                    else:
                        return url_for("user_dashboard")
                
                else:
                    return render_template("login.html", error="Invalid Password")
        return render_template("login.html")
    
    @app.route("/admin")
    def admin_dashboard():
        if "role" not in session:
            return redirect(url_for("login.html"))
        
        if session["role"] != "ADMIN":
            return redirect(url_for("login.html"))
        
        return render_template("admin_dashboard.html", name=session["name"])
    
    @app.route("/staff")
    def staff_dashboard():

        if "role" not in session:
            return redirect(url_for("login"))

        if session["role"] != "staff":
            return redirect(url_for("login"))

        return render_template("staff_dashboard.html", name=session["name"])
    
    @app.route("/user")
    def user_dashboard():
        if "role" not in session:
            return redirect(url_for("login.html"))
        
        return render_template("user_dashboard.html", name=session["name"])
    
    @app.route("/register", methods=["GET", "POST"])
    def register():

        if request.method == "POST":
            name = request.form["name"]
            email = request.form["email"]
            phone = request.form["phone"]
            password = request.form["password"]
            confirm_password = request.form["confirm_password"]
            role = request.form["role"]

            if password != confirm_password:
                return render_template(
                    "register.html",
                    error="Passwords do not match"
                )

            with Session(engine) as db:
                existing_user = db.query(User).filter(
                    User.email == email
                ).first()

                if existing_user:
                    return render_template(
                        "register.html",
                        error="Email already registered"
                    )

                new_user = User(name=name, email=email, role=role,phone=phone)
                new_user.set_password(password)
                db.add(new_user)
                db.commit()

                if role == "staff":
                    staff = StaffProfile(userid=new_user.userid)
                    db.add(staff)
                    db.commit()
            return redirect(url_for("login"))
        
        return render_template("register.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login.html"))
