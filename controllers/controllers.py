from flask import app, render_template, request, redirect, url_for, session, flash
from models.models import engine, User, StaffProfile, Trek, Booking
from sqlalchemy.orm import Session
from datetime import datetime

def init_app_routes(app):
    @app.route("/", methods=["GET", "POST"])
    def login():
        if request.method == "POST":

            email = request.form["email"].lower()
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
                        return redirect(url_for("admin_dashboard"))
                    elif user.role == "staff":
                        staff = db.query(StaffProfile).filter(StaffProfile.userid == user.userid).first()
                        if staff.approval_status != "Approved":
                            session.clear()
                            return render_template("login.html", error="Your account is awaiting admin approval.")
                        return redirect(url_for("staff_dashboard"))
                    else:
                        return redirect(url_for("user_dashboard"))
                
                else:
                    return render_template("login.html", error="Invalid Password")
        return render_template("login.html")
    
    @app.route("/admin")
    def admin_dashboard():
        if "role" not in session or session["role"] != "admin":
            return redirect(url_for("login"))
        
        with Session(engine) as db:
            total_treks = db.query(Trek).count()
            total_users = db.query(User).filter(User.role == 'user').count()
            total_staff = db.query(StaffProfile).count()
            total_bookings = db.query(Booking).count()

            stats = {
                'total_treks': total_treks,
                'total_users': total_users,
                'total_staff': total_staff,
                'total_bookings': total_bookings
            }

            recent_bookings = (
                db.query(Booking)
                .join(User, Booking.userid == User.userid)
                .join(Trek, Booking.trekid == Trek.trekid)
                .order_by(Booking.booking_date.desc())
                .limit(5)
                .all()
            )

            bookings_data = []
            for b in recent_bookings:
                bookings_data.append({
                    'id': f"B{b.bookingid:03d}",
                    'user_name': b.user.name,
                    'trek_title': b.trek.trekname,
                    'booking_date': b.booking_date.strftime('%d %b %Y') if b.booking_date else '',
                    'status': b.booking_status
                })
        
        return render_template("dashboard.html", name=session["name"], stats=stats, bookings=bookings_data, active_page='dashboard')
    

    @app.route("/admin/treks")
    def admin_treks():
        if "role" not in session or session["role"] != "admin":
            return redirect(url_for("login"))
        
        # Get parameters from request
        search_query = request.args.get('search', '').strip()
        status_filter = request.args.get('status', 'All').strip()
        
        try:
            page = int(request.args.get('page', 1))
            if page < 1: page = 1
        except ValueError:
            page = 1

        PER_PAGE = 5

        with Session(engine) as db:
            # Build base query
            query = db.query(Trek)
            
            # Apply search condition (searches by name or location)
            if search_query:
                query = query.filter(
                    (Trek.trekname.ilike(f"%{search_query}%")) | 
                    (Trek.location.ilike(f"%{search_query}%"))
                )
                
            # Apply status filter condition
            if status_filter and status_filter != 'All':
                query = query.filter(Trek.status == status_filter)

            # Count total filtered items for pagination
            total_items = query.count()
            total_pages = (total_items + PER_PAGE - 1) // PER_PAGE if total_items > 0 else 1

            # Adjust page number if it exceeds total pages after filtering
            if page > total_pages:
                page = total_pages
                if page < 1: page = 1

            offset = (page - 1) * PER_PAGE
            
            # Fetch filtered, paginated results
            all_treks = query.order_by(Trek.trekid.desc()).offset(offset).limit(PER_PAGE).all()

            treks_data = []
            for t in all_treks:
                treks_data.append({
                    'raw_id': t.trekid,
                    'id': t.trekid,
                    'name': t.trekname,
                    'location': t.location if t.location else 'N/A',
                    'difficulty': t.difficulty if t.difficulty else 'Easy',
                    'slots': t.total_slots,
                    'status': t.status if t.status else 'Open'
                })
        
        return render_template(
            "treks.html", 
            name=session["name"], 
            treks=treks_data, 
            current_page=page,
            total_pages=total_pages,
            search_query=search_query,
            status_filter=status_filter,
            active_page='treks'
        )
    
    @app.route("/admin/users")
    def admin_users():
        if "role" not in session or session["role"] != "admin":
            return redirect(url_for("login"))
            
        page = int(request.args.get('page', 1))
        search_query = request.args.get('search', '').strip()
        PER_PAGE = 5

        with Session(engine) as db:
            query = db.query(User).filter(User.role == 'user')

            if search_query:
                search_filter = f"%{search_query}%"
                query = query.filter(
                    (User.name.like(search_filter)) | 
                    (User.email.like(search_filter)) |
                    (User.phone.like(search_filter))
                )

            total_items = query.count()
            total_pages = (total_items + PER_PAGE - 1) // PER_PAGE if total_items > 0 else 1
            
            offset = (page - 1) * PER_PAGE
            paginated_users = query.order_by(User.userid.desc()).offset(offset).limit(PER_PAGE).all()

            users_list = []
            for u in paginated_users:
                users_list.append({
                    'raw_id': u.userid,
                    'id': f"U{u.userid:03d}",
                    'name': u.name,
                    'email': u.email,
                    'contact': u.phone if u.phone else 'N/A',
                    'status': 'Open' if u.is_active else 'Blacklisted',
                    'is_active': u.is_active
                })

        return render_template(
            "admin_users.html",
            users_list=users_list,
            current_page=page,
            total_pages=total_pages,
            search_query=search_query,
            active_page='users'
        )

    @app.route("/admin/users/toggle/<int:user_id>", methods=["POST"])
    def toggle_user_status(user_id):
        if "role" not in session or session["role"] != "admin":
            return redirect(url_for("login"))

        with Session(engine) as db:
            target_user = db.query(User).filter(User.userid == user_id).first()
            if target_user:
                target_user.is_active = not target_user.is_active
                db.commit()

        return redirect(url_for('admin_users', search=request.args.get('search', '')))
    
    @app.route("/admin/bookings")
    def admin_booking():
        if "role" not in session or session["role"] != "admin":
            return redirect(url_for("login"))
            
        page = int(request.args.get('page', 1))
        search_query = request.args.get('search', '').strip()
        PER_PAGE = 5

        with Session(engine) as db:
            # Base database query fetching bookings
            query = db.query(Booking)

            # Simple string-matching search filter across related tables
            if search_query:
                search_filter = f"%{search_query}%"
                query = query.join(Booking.user).join(Booking.trek).filter(
                    (User.name.like(search_filter)) | 
                    (Trek.trekname.like(search_filter))
                )

            total_items = query.count()
            total_pages = (total_items + PER_PAGE - 1) // PER_PAGE if total_items > 0 else 1
            
            offset = (page - 1) * PER_PAGE
            paginated_bookings = query.order_by(Booking.bookingid.desc()).offset(offset).limit(PER_PAGE).all()

            bookings_list = []
            for b in paginated_bookings:
                bookings_list.append({
                    'raw_id': b.bookingid,
                    'id': f"B{b.bookingid:03d}",
                    'user_name': b.user.name if b.user else "Unknown User",
                    'trek_title': b.trek.trekname if b.trek else "Unknown Trek",
                    'booking_date': b.booking_date.strftime('%Y-%m-%d'),
                    'status': b.booking_status  # e.g., 'Booked' or 'Cancelled'
                })

        return render_template(
            "admin_bookings.html",
            bookings_list=bookings_list,
            current_page=page,
            total_pages=total_pages,
            search_query=search_query,
            active_page='bookings'
        )

    @app.route("/admin/bookings/update/<int:booking_id>/<string:action>", methods=["POST"])
    def update_booking_status(booking_id, action):
        if "role" not in session or session["role"] != "admin":
            return redirect(url_for("login"))

        with Session(engine) as db:
            booking = db.query(Booking).filter(Booking.bookingid == booking_id).first()
            if booking:
                if action == 'cancel':
                    booking.status = 'Cancelled'
                elif action == 'restore':
                    booking.status = 'Booked'
                db.commit()

        return redirect(url_for('admin_bookings', search=request.args.get('search', '')))
    
    @app.route("/admin/treks/add", methods=["GET", "POST"])
    def add_trek():
        if "role" not in session or session["role"] != "admin":
            return redirect(url_for("login"))
        
        if request.method == "POST":
            name = request.form.get("trekname")
            location = request.form.get("location")
            difficulty = request.form.get("difficulty")
            duration = request.form.get("duration")
            slots = request.form.get("slots")
            status = request.form.get("status")
            description = request.form.get("description")
            staff_id = request.form.get("staff_id")

            start_date = datetime.strptime(request.form.get("start_date"), '%Y-%m-%d').date() if request.form.get("start_date") else None
            end_date = datetime.strptime(request.form.get("end_date"), '%Y-%m-%d').date() if request.form.get("end_date") else None
            
            with Session(engine) as db:
                new_trek = Trek(
                    trekname=name,
                    location=location,
                    difficulty=difficulty,
                    duration=int(duration) if duration else None,
                    slots=int(slots) if slots else 0,
                    status=status,
                    description=description,
                    staff_id=int(staff_id) if staff_id else None # Maps to your model's staff relationship setup
                )
                db.add(new_trek)
                db.commit()
                
            return redirect(url_for("admin_treks"))

        with Session(engine) as db:
            db_staff = db.query(StaffProfile).all()
            staff_list = [{'id': s.staffid, 'name': s.user.name} for s in db_staff] if db_staff else []

        return render_template("admin_add_trek.html", staff_list=staff_list, active_page='treks')

    @app.route("/admin/treks/edit/<int:trek_id>", methods=["GET", "POST"])
    def edit_trek(trek_id):
        if "role" not in session or session["role"] != "admin":
            return redirect(url_for("login"))

        with Session(engine) as db:
            trek = db.query(Trek).filter(Trek.trekid == trek_id).first()
            if not trek:
                return "Trek record not found", 404

            if request.method == "POST":
                trek.trekname = request.form.get("trekname")
                trek.location = request.form.get("location")
                trek.difficulty = request.form.get("difficulty")
                trek.duration = int(request.form.get("duration"))
                trek.description = request.form.get("description")
                trek.assigned_staff = int(request.form.get("staff_id"))
                trek.status = request.form.get("status")
                trek.start_date = datetime.strptime(request.form.get("start_date"), "%Y-%m-%d").date()
                trek.end_date = datetime.strptime(request.form.get("end_date"), "%Y-%m-%d").date()
                
                new_total = int(request.form.get("slots"))
                difference = new_total - trek.total_slots
                trek.total_slots = new_total
                trek.available_slots = max(0, trek.available_slots + difference)
                
                db.commit()
                return redirect(url_for("admin_treks"))

            approved_staff = db.query(StaffProfile).filter(StaffProfile.approval_status == 'Approved').all()
            staff_list = [{'id': s.staffid, 'name': s.user.name} for s in approved_staff]

            return render_template("admin_add_trek.html", staff_list=staff_list, trek=trek)

    @app.route("/admin/treks/delete/<int:trek_id>", methods=["POST"])
    def delete_trek(trek_id):
        if "role" not in session or session["role"] != "admin":
            return redirect(url_for("login"))

        with Session(engine) as db:
            trek = db.query(Trek).filter(Trek.trekid == trek_id).first()
            if trek:
                db.delete(trek)
                db.commit()
                
        return redirect(url_for("admin_treks"))

    @app.route("/admin/staff")
    def admin_staff():
        if "role" not in session or session["role"] != "admin":
            return redirect(url_for("login"))
        
        current_tab = request.args.get('tab', 'pending').lower()
        
        with Session(engine) as db:
            pending_count = db.query(StaffProfile).filter(StaffProfile.approval_status == 'Pending').count()
            approved_count = db.query(StaffProfile).filter(StaffProfile.approval_status == 'Approved').count()
            blacklisted_count = db.query(StaffProfile).filter(StaffProfile.approval_status == 'Blacklisted').count()
            
            counts = {
                'pending': pending_count,
                'approved': approved_count,
                'blacklisted': blacklisted_count
            }
            
            target_status = current_tab.capitalize()
            query_results = db.query(StaffProfile).filter(StaffProfile.approval_status == target_status).all()
            

            staff_data = []
            for s in query_results:
                staff_data.append({
                    'raw_id': s.staffid,
                    'id': f"S{s.staffid:03d}",
                    'name': s.user.name,
                    'email': s.user.email,
                    'contact': s.user.phone,
                    'status': s.approval_status
                })
                
        return render_template("admin_staff.html", staff_members=staff_data, counts=counts, active_tab=current_tab, active_page='staff')

    @app.route("/admin/staff/update/<int:staff_id>/<string:action>", methods=["POST"])
    def update_staff_status(staff_id, action):
        if "role" not in session or session["role"] != "admin":
            return redirect(url_for("login"))
            
        target_tab = request.args.get('origin', 'pending')
            
        with Session(engine) as db:
            member = db.query(StaffProfile).filter(StaffProfile.staffid == staff_id).first()
            if member:
                if action == 'approve':
                    member.approval_status = 'Approved'
                elif action == 'reject':
                    member.approval_status = 'Rejected' 
                elif action == 'blacklist':
                    member.approval_status = 'Blacklisted'
                db.commit()
                
        return redirect(url_for('admin_staff', tab=target_tab))

    @app.route("/register", methods=["GET", "POST"])
    def register():

        if request.method == "POST":
            name = request.form["name"]
            email = request.form["email"].lower()
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

    @app.route("/staff/dashboard")
    def staff_dashboard():
        if "role" not in session or session["role"] != "staff":
            return redirect(url_for("login"))
            
        user_id = session.get("userid")

        with Session(engine) as db:
            staff_profile = db.query(StaffProfile).filter(StaffProfile.userid == user_id).first()
            
            if not staff_profile:
                return "Staff profile record missing.", 404

            assigned_treks = db.query(Trek).filter(Trek.assigned_staff == staff_profile.staffid).all()
            
            total_assigned = len(assigned_treks)
            open_treks_count = sum(1 for t in assigned_treks if t.status.lower() == 'open')
            
            total_participants = 0
            assigned_treks_list = []
            
            for t in assigned_treks:
                participant_count = db.query(Booking).filter(
                    Booking.trekid == t.trekid, 
                    Booking.booking_status == 'Booked'
                ).count() if 'Booking' in globals() else 0
                
                total_participants += participant_count
                if t.status == "Open":
                    assigned_treks_list.append({
                        'id': t.trekid,
                        'name': t.trekname,
                        'location': t.location,
                        'participants': participant_count,
                        'slots': t.total_slots,
                        'status': t.status
                    })

            stats = {
                'assigned_treks': total_assigned,
                'total_participants': total_participants,
                'open_treks': open_treks_count
            }

        return render_template(
            "staff_dashboard.html",
            stats=stats,
            assigned_treks_list=assigned_treks_list,
            active_page='dashboard'
        )

    @app.route("/staff/treks")
    def staff_treks():
        if "role" not in session or session["role"] != "staff":
            return redirect(url_for("login"))

        try:
            page = int(request.args.get("page", 1))
            if page < 1:
                page = 1
        except ValueError:
            page = 1

        search_query = request.args.get("search", "").strip()
        status_filter = request.args.get("status", "All")

        PER_PAGE = 5

        with Session(engine) as db:
            staff_profile = db.query(StaffProfile).filter(
                StaffProfile.userid == session["userid"]
            ).first()

            if not staff_profile:
                return "Staff profile entry missing."

            query = db.query(Trek).filter(
                Trek.assigned_staff == staff_profile.staffid
            )
            if status_filter != "All":
                query = query.filter(Trek.status == status_filter)

            if search_query:
                query = query.filter(
                    (Trek.trekname.ilike(f"%{search_query}%")) |
                    (Trek.location.ilike(f"%{search_query}%"))
                )

            total_items = query.count()
            total_pages = (total_items + PER_PAGE - 1) // PER_PAGE if total_items else 1
            offset = (page - 1) * PER_PAGE

            my_treks = (
                query.order_by(Trek.start_date.asc())
                    .offset(offset)
                    .limit(PER_PAGE)
                    .all()
            )

            assigned_treks_data = []

            for t in my_treks:
                assigned_treks_data.append({
                    "raw_id": t.trekid,
                    "name": t.trekname,
                    "location": t.location,
                    "difficulty": t.difficulty,
                    "slots": f"{t.available_slots}/{t.total_slots}",
                    "status": t.status
                })

        return render_template(
            "staff_treks.html",
            assigned_treks=assigned_treks_data,
            current_page=page,
            total_pages=total_pages,
            search_query=search_query,
            status_filter=status_filter,
            active_page="treks"
        )

    @app.route("/staff/manage-trek/<int:trek_id>")
    def staff_manage_trek(trek_id):
        if "role" not in session or session["role"] != "staff":
            return redirect(url_for("login"))

        with Session(engine) as db:
            trek = db.query(Trek).filter(Trek.trekid == trek_id).first()
            if not trek:
                return "Trek variant error or not found.", 404

            active_bookings = db.query(Booking).filter(Booking.trekid == trek_id).all()
            
            participants_data = []
            for b in active_bookings:
                participants_data.append({
                    'user_name': b.user.name,
                    'email': b.user.email,
                    'booking_date': b.booking_date.strftime('%d %b %Y'),
                    'status': b.booking_status
                })

            return render_template(
                "staff_manage_trek.html", 
                trek=trek, 
                participants=participants_data,
                active_page='treks'
            )

    @app.route("/staff/manage-trek/config/<int:trek_id>", methods=["POST"])
    def staff_update_trek_config(trek_id):
        if "role" not in session or session["role"] != "staff":
            return redirect(url_for("login"))

        with Session(engine) as db:
            trek = db.query(Trek).filter(Trek.trekid == trek_id).first()
            if trek:
                trek.available_slots = int(request.form.get("available_slots"))
                trek.status = request.form.get("status")
                db.commit()
                
        return redirect(url_for("staff_manage_trek", trek_id=trek_id))

    @app.route("/staff/manage-trek/lifecycle/<int:trek_id>/<next_state>", methods=["POST"])
    def staff_change_status(trek_id, next_state):
        if "role" not in session or session["role"] != "staff":
            return redirect(url_for("login"))

        with Session(engine) as db:
            trek = db.query(Trek).filter(Trek.trekid == trek_id).first()
            if trek and next_state in ['Started', 'Completed']:
                trek.status = next_state
                db.commit()
                
        return redirect(url_for("staff_manage_trek", trek_id=trek_id))

    @app.route("/staff/participants")
    def staff_participants():
        if "role" not in session or session["role"] != "staff":
            return redirect(url_for("login"))

        search_query = request.args.get("search", "").strip()
        status_filter = request.args.get("status", "All")
        trek_filter = request.args.get("trek", "All")

        with Session(engine) as db:
            staff_profile = db.query(StaffProfile).filter(
                StaffProfile.userid == session["userid"]
            ).first()

            if not staff_profile:
                return "Staff profile entry missing.", 404

            trek_list = (
                db.query(Trek)
                .filter(Trek.assigned_staff == staff_profile.staffid)
                .order_by(Trek.trekname)
                .all()
            )

            bookings_query = (
                db.query(Booking)
                .join(Trek, Booking.trekid == Trek.trekid)
                .join(User, Booking.userid == User.userid)
                .filter(Trek.assigned_staff == staff_profile.staffid)
            )

            if search_query:
                bookings_query = bookings_query.filter(
                    User.name.ilike(f"%{search_query}%") |
                    User.email.ilike(f"%{search_query}%") |
                    Trek.trekname.ilike(f"%{search_query}%")
                )

            if status_filter != "All":
                bookings_query = bookings_query.filter(
                    Booking.booking_status == status_filter
                )

            if trek_filter != "All":
                bookings_query = bookings_query.filter(
                    Booking.trekid == int(trek_filter)
                )

            bookings = (
                bookings_query
                .order_by(Booking.booking_date.desc())
                .all()
            )

            participants_data = []

            for b in bookings:
                participants_data.append({
                    "user_name": b.user.name,
                    "email": b.user.email,
                    "phone": b.user.phone,
                    "trek_title": b.trek.trekname,
                    "booking_date": b.booking_date.strftime("%d %b %Y"),
                    "status": b.booking_status
                })

        return render_template(
            "staff_participants.html",
            participants=participants_data,
            trek_list=trek_list,
            search_query=search_query,
            status_filter=status_filter,
            trek_filter=trek_filter,
            active_page="participants"
        )

    @app.route("/staff/profile", methods=["GET", "POST"])
    def staff_profile():
        if "role" not in session or session["role"] != "staff":
            return redirect(url_for("login"))

        with Session(engine) as db:
            user = db.query(User).filter(
                User.userid == session["userid"]
            ).first()

            staff = db.query(StaffProfile).filter(
                StaffProfile.userid == session["userid"]
            ).first()

            if not user or not staff:
                return "Staff profile not found.", 404

            if request.method == "POST":
                user.name = request.form["name"].strip()
                user.phone = request.form["phone"].strip()

                db.commit()

                flash("Profile updated successfully!", "success")
                return redirect(url_for("staff_profile"))

            assigned_trek_count = db.query(Trek).filter(
                Trek.assigned_staff == staff.staffid
            ).count()

        return render_template(
            "staff_profile.html",
            user=user,
            staff=staff,
            assigned_trek_count=assigned_trek_count,
            active_page="profile"
        )

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))
