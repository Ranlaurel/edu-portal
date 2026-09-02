# Deployment Checklist for edu.rvnza.ru

## ✅ Pre-Deployment

### 1. Environment Variables
Ensure the following are set on production server:

```bash
export EDU_PORTAL_SECRET_KEY="<generate-strong-random-key>"
export EDU_PORTAL_LOGIN="admin"
export EDU_PORTAL_PASSWORD="<secure-admin-password>"
```

**Generate SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Database Setup
```bash
# Backup existing database (if any)
cp portal.db portal.db.backup.$(date +%Y%m%d-%H%M%S)

# Load content for both grades
.venv/bin/python pipeline/load_content.py

# Verify data loaded
.venv/bin/python -c "from app.db import SessionLocal; from app.models import Subject, Topic, User; db=SessionLocal(); print(f'Subjects: {db.query(Subject).count()}, Topics: {db.query(Topic).count()}, Users: {db.query(User).count()}'); db.close()"
```

Expected output:
- Subjects: 15 (7 for grade 5, 8 for grade 6)
- Topics: 562
- Users: 3 (admin, Ranlaurel4, Shvedko1)

### 3. File Permissions
```bash
chmod 600 portal.db
chmod 700 .venv
```

### 4. Dependencies
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 🚀 Deployment Steps

### 1. Pull Latest Code
```bash
git pull origin main
```

### 2. Restart Application
If using systemd:
```bash
sudo systemctl restart edu-portal
```

If using PM2:
```bash
pm2 restart edu-portal
```

If using manual uvicorn:
```bash
pkill -f uvicorn
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 &
```

### 3. Verify Server Started
```bash
curl http://localhost:8000/login
# Should return 200 OK
```

---

## ✅ Post-Deployment Verification

### 1. Login Test
- Navigate to https://edu.rvnza.ru/login
- Test admin login
- Test Ranlaurel4 login (елисей2018)
- Test Shvedko1 login (анжелика2017)

### 2. User Display Names
- ✅ Ranlaurel4 shows "Елисей С." in header
- ✅ Shvedko1 shows "Анжелика Ш." in header

### 3. Grade Switching
- ✅ Select grade 5 → subjects list shows 7 subjects
- ✅ Select grade 6 → subjects list shows 8 subjects
- ✅ Schedule loads for both grades (166 days each)

### 4. Dashboard
- ✅ Dashboard shows correct progress for logged-in user
- ✅ Heatmap renders
- ✅ Week/weak/recent sections populated

### 5. Mobile Test
- Open on mobile device (375px width)
- ✅ No horizontal scrolling on subject list
- ✅ Schedule scrolls horizontally within container
- ✅ Navigation wraps correctly

### 6. Browser Console
- ✅ No JavaScript errors in console

---

## 🔒 Security Checks

### Before Going Live

- [ ] Change default passwords for Ranlaurel4 and Shvedko1
- [ ] Set strong EDU_PORTAL_SECRET_KEY (not default)
- [ ] Set strong admin password
- [ ] Consider adding CSRF protection (starlette-wtf)
- [ ] Consider adding rate limiting on /login
- [ ] Verify portal.db is not world-readable (chmod 600)

### Optional Enhancements

- [ ] Add SSL certificate (Let's Encrypt)
- [ ] Set up automated backups for portal.db
- [ ] Add logging for login attempts
- [ ] Set up monitoring/alerts

---

## 🐛 Troubleshooting

### Database locked
```bash
# Check for zombie processes
ps aux | grep python
kill -9 <pid>
```

### Missing content
```bash
# Re-run content loader
.venv/bin/python pipeline/load_content.py
```

### Session errors
```bash
# Regenerate secret key and restart
export EDU_PORTAL_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
sudo systemctl restart edu-portal
```

### Users not showing display names
```bash
# Verify migration ran
.venv/bin/python -c "from app.db import SessionLocal, engine; from sqlalchemy import text; db=SessionLocal(); print([r[1] for r in db.execute(text('PRAGMA table_info(users)'))]); db.close()"
# Should include 'display_name'
```

---

## 📊 Monitoring

### Check Application Logs
```bash
# systemd
journalctl -u edu-portal -f

# PM2
pm2 logs edu-portal

# Manual
tail -f nohup.out
```

### Database Size
```bash
du -h portal.db
# Should be ~15-20MB with full content
```

---

## 🎯 Success Criteria

- [x] Code committed: `c3b284d`
- [ ] Server restarted successfully
- [ ] All 3 users can log in
- [ ] Display names show correctly
- [ ] Both grades (5 & 6) accessible
- [ ] Dashboard shows user-specific progress
- [ ] Mobile viewport renders correctly
- [ ] No console errors

---

## 📝 Notes

- Test users have pre-populated progress (18 topics for Ranlaurel4, 12 for Shvedko1)
- Grade 5 content includes 7 subjects with 166-day schedule
- Grade 6 content remains unchanged (8 subjects, 166-day schedule)
- CSS version bumped to `?v=2` for cache-busting

---

## 🆘 Rollback Plan

If critical issues arise:

```bash
# Restore database backup
cp portal.db.backup.YYYYMMDD-HHMMSS portal.db

# Revert to previous commit
git revert c3b284d

# Restart application
sudo systemctl restart edu-portal
```
