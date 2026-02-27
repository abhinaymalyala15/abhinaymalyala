(function () {
    'use strict';

    var mainContent = document.getElementById('mainContent');
    var toastContainer = document.getElementById('toastContainer');
    var pages = ['dashboard', 'sections', 'students', 'mark', 'records', 'settings'];
    var navItems = document.querySelectorAll('.nav-item[data-page]');
    var sectionsCache = [];
    var currentMarkSectionId = null;
    var currentMarkDate = null;
    var currentMarkSession = null;
    var markAttendanceStudents = [];
    var markEditingMode = false;

    function escapeHtml(s) {
        if (s == null) return '';
        var div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    function showPage(pageId) {
        pages.forEach(function (p) {
            var el = document.getElementById('page' + p.charAt(0).toUpperCase() + p.slice(1));
            if (el) el.classList.toggle('active', p === pageId);
        });
        navItems.forEach(function (n) {
            n.classList.toggle('active', n.getAttribute('data-page') === pageId);
            n.setAttribute('aria-current', n.getAttribute('data-page') === pageId ? 'page' : null);
        });
        if (pageId === 'dashboard') renderDashboard();
        else if (pageId === 'sections') renderSections();
        else if (pageId === 'students') renderStudents();
        else if (pageId === 'mark') renderMarkAttendance();
        else if (pageId === 'records') renderRecords();
        else if (pageId === 'settings') renderSettings();
        else if (pageId === 'logout') window.location.reload();
    }

    function toast(message, type) {
        type = type || 'success';
        var el = document.createElement('div');
        el.className = 'toast ' + type;
        el.setAttribute('role', 'alert');
        el.textContent = message;
        toastContainer.appendChild(el);
        setTimeout(function () {
            if (el.parentNode) el.parentNode.removeChild(el);
        }, 3500);
    }

    function api(path, options) {
        options = options || {};
        var method = options.method || 'GET';
        var body = options.body;
        return fetch(path, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: body ? JSON.stringify(body) : undefined
        }).then(function (r) {
            if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || 'Request failed'); });
            return r.json();
        });
    }

    // ----- Dashboard -----
    function renderDashboard() {
        var wrap = document.getElementById('pageDashboard');
        wrap.innerHTML = '<div class="page-header"><h2>Dashboard</h2><p>Overview of your attendance system</p></div><div class="cards-grid" id="dashboardCards">Loading…</div>';
        api('/api/dashboard/stats').then(function (data) {
            document.getElementById('dashboardCards').innerHTML =
                '<div class="summary-card"><div class="card-label">Total Sections</div><div class="card-value">' + (data.total_sections || 0) + '</div></div>' +
                '<div class="summary-card"><div class="card-label">Total Students</div><div class="card-value">' + (data.total_students || 0) + '</div></div>' +
                '<div class="summary-card"><div class="card-label">Attendance Marked Today</div><div class="card-value">' + (data.attendance_marked_today || 0) + '</div></div>' +
                '<div class="summary-card"><div class="card-label">Total Absentees Today</div><div class="card-value">' + (data.absent_today || 0) + '</div></div>';
        }).catch(function () {
            document.getElementById('dashboardCards').innerHTML = '<div class="empty-state">Failed to load stats.</div>';
        });
    }

    // ----- Sections -----
    function renderSections() {
        var wrap = document.getElementById('pageSections');
        wrap.innerHTML = '<div class="page-header"><h2>Sections</h2><p>Manage sections</p></div><div class="actions-row"><button type="button" class="btn btn-primary" id="btnAddSection">+ Add Section</button></div><div class="section-cards" id="sectionCards">Loading…</div>';
        api('/api/sections?stats=1').then(function (list) {
            sectionsCache = list || [];
            var cards = document.getElementById('sectionCards');
            if (sectionsCache.length === 0) {
                cards.innerHTML = '<div class="empty-state">No sections. Click Add Section.</div>';
                return;
            }
            cards.innerHTML = sectionsCache.map(function (s) {
                var marked = s.attendance_marked_today ? 'Yes' : 'No';
                return '<div class="section-card" data-id="' + s.id + '"><h3>' + escapeHtml(s.name) + '</h3><div class="meta">Students: ' + (s.student_count || 0) + '</div><span class="badge ' + (s.attendance_marked_today ? 'yes' : 'no') + '">Marked today: ' + marked + '</span><div class="actions-row" style="margin-top:12px"><button type="button" class="btn btn-sm btn-secondary btn-edit-section" data-id="' + s.id + '">Edit</button><button type="button" class="btn btn-sm btn-danger btn-delete-section" data-id="' + s.id + '">Delete</button></div></div>';
            }).join('');
            cards.querySelectorAll('.btn-edit-section').forEach(function (b) {
                b.addEventListener('click', function (e) { e.stopPropagation(); openSectionModal(parseInt(b.getAttribute('data-id'), 10)); });
            });
            cards.querySelectorAll('.btn-delete-section').forEach(function (b) {
                b.addEventListener('click', function (e) { e.stopPropagation(); confirmDeleteSection(parseInt(b.getAttribute('data-id'), 10)); });
            });
        }).catch(function () {
            document.getElementById('sectionCards').innerHTML = '<div class="empty-state">Failed to load.</div>';
        });
        document.getElementById('btnAddSection').onclick = function () { openSectionModal(null); };
    }

    function openSectionModal(id) {
        var title = document.getElementById('modalSectionTitle');
        var nameInput = document.getElementById('sectionName');
        var form = document.getElementById('formSection');
        if (id != null) {
            var s = sectionsCache.find(function (x) { return x.id === id; });
            title.textContent = 'Edit Section';
            nameInput.value = s ? s.name : '';
            form.dataset.editId = id;
        } else {
            title.textContent = 'Add Section';
            nameInput.value = '';
            delete form.dataset.editId;
        }
        document.getElementById('modalSection').classList.add('show');
    }

    function closeSectionModal() {
        document.getElementById('modalSection').classList.remove('show');
    }

    document.getElementById('formSection').addEventListener('submit', function (e) {
        e.preventDefault();
        var name = document.getElementById('sectionName').value.trim();
        if (!name) return;
        var id = this.dataset.editId;
        var req = id ? api('/api/sections/' + id, { method: 'PATCH', body: { name: name } }) : api('/api/sections', { method: 'POST', body: { name: name } });
        req.then(function () {
            closeSectionModal();
            toast('Section saved.');
            renderSections();
        }).catch(function (err) {
            toast(err.message, 'error');
        });
    });
    document.querySelector('.btn-cancel-section').onclick = closeSectionModal;
    document.getElementById('modalSection').onclick = function (e) { if (e.target === this) closeSectionModal(); };

    function confirmDeleteSection(id) {
        var s = sectionsCache.find(function (x) { return x.id === id; });
        document.getElementById('modalConfirmTitle').textContent = 'Delete Section';
        document.getElementById('modalConfirmBody').textContent = 'Delete section "' + (s ? s.name : '') + '"? All students and attendance in this section will be removed.';
        document.getElementById('modalConfirm').classList.add('show');
        document.getElementById('btnConfirmOk').onclick = function () {
            api('/api/sections/' + id, { method: 'DELETE' }).then(function () {
                document.getElementById('modalConfirm').classList.remove('show');
                toast('Section deleted.');
                renderSections();
            }).catch(function (err) {
                toast(err.message, 'error');
            });
        };
    }

    document.getElementById('btnConfirmCancel').onclick = function () { document.getElementById('modalConfirm').classList.remove('show'); };
    document.getElementById('modalConfirm').onclick = function (e) { if (e.target === this) this.classList.remove('show'); };

    // ----- Students -----
    var studentsPage = 1, studentsPerPage = 25, studentsTotal = 0, studentsSectionId = null, studentsSearch = '', studentsSortBy = 'roll_no';

    function renderStudents() {
        var wrap = document.getElementById('pageStudents');
        wrap.innerHTML = '<div class="page-header"><h2>Students</h2><p>Manage students</p></div>' +
            '<div class="actions-row"><input type="text" class="search-input" id="studentsSearch" placeholder="Search roll or name"><select id="studentsSectionFilter"><option value="">All sections</option></select><select id="studentsPerPage"><option value="10">10 per page</option><option value="25" selected>25 per page</option><option value="50">50 per page</option></select><button type="button" class="btn btn-primary" id="btnAddStudent">+ Add Student</button></div>' +
            '<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Roll No <button type="button" class="btn btn-sm btn-secondary sort-btn" data-sort="roll_no">↕</button></th><th>Name <button type="button" class="btn btn-sm btn-secondary sort-btn" data-sort="name">↕</button></th><th>Section</th><th></th></tr></thead><tbody id="studentsTbody"></tbody></table></div>' +
            '<div class="pagination-bar" id="studentsPagination"></div>';
        loadSectionsForSelect(document.getElementById('studentsSectionFilter'));
        loadStudentsList();
        document.getElementById('studentsSearch').oninput = function () { studentsSearch = this.value; studentsPage = 1; loadStudentsList(); };
        document.getElementById('studentsSectionFilter').onchange = function () { studentsSectionId = this.value ? parseInt(this.value, 10) : null; studentsPage = 1; loadStudentsList(); };
        document.getElementById('studentsPerPage').onchange = function () { studentsPerPage = parseInt(this.value, 10); studentsPage = 1; loadStudentsList(); };
        document.getElementById('btnAddStudent').onclick = function () { openStudentModal(null); };
        document.querySelectorAll('.sort-btn').forEach(function (b) {
            b.onclick = function () { studentsSortBy = this.getAttribute('data-sort'); loadStudentsList(); };
        });
    }

    function loadSectionsForSelect(selectEl) {
        api('/api/sections').then(function (list) {
            var opts = (list || []).map(function (s) { return '<option value="' + s.id + '">' + escapeHtml(s.name) + '</option>'; }).join('');
            selectEl.innerHTML = '<option value="">All sections</option>' + opts;
        });
    }

    function loadStudentsList() {
        var q = '?page=' + studentsPage + '&per_page=' + studentsPerPage + '&sort_by=' + studentsSortBy;
        if (studentsSectionId) q += '&section_id=' + studentsSectionId;
        if (studentsSearch) q += '&search=' + encodeURIComponent(studentsSearch);
        api('/api/students' + q).then(function (data) {
            var list = data.students || [];
            studentsTotal = data.total || 0;
            return api('/api/sections').then(function (secList) {
                var sectionsByName = {};
                (secList || []).forEach(function (s) { sectionsByName[s.id] = s.name; });
                return { list: list, sectionsByName: sectionsByName };
            });
        }).then(function (out) {
            var list = out.list;
            var sectionsByName = out.sectionsByName;
            var tbody = document.getElementById('studentsTbody');
            tbody.innerHTML = list.map(function (st) {
                var secName = sectionsByName[st.section_id] || '—';
                return '<tr><td>' + escapeHtml(st.roll_no) + '</td><td>' + escapeHtml(st.name) + '</td><td>' + escapeHtml(secName) + '</td><td><button type="button" class="btn btn-sm btn-secondary btn-edit-student" data-id="' + st.id + '">Edit</button> <button type="button" class="btn btn-sm btn-danger btn-delete-student" data-id="' + st.id + '">Delete</button></td></tr>';
                }).join('');
            tbody.querySelectorAll('.btn-edit-student').forEach(function (b) {
                b.onclick = function () { openStudentModal(parseInt(b.getAttribute('data-id'), 10)); };
            });
            tbody.querySelectorAll('.btn-delete-student').forEach(function (b) {
                b.onclick = function () { confirmDeleteStudent(parseInt(b.getAttribute('data-id'), 10)); };
            });
            var totalPages = Math.ceil(studentsTotal / studentsPerPage) || 1;
            var pag = document.getElementById('studentsPagination');
            pag.innerHTML = '<span>Total: ' + studentsTotal + '</span>';
            if (totalPages > 1) {
                pag.innerHTML += ' <button type="button" class="btn btn-sm btn-secondary btn-page" data-page="prev">Previous</button> <span>Page ' + studentsPage + ' of ' + totalPages + '</span> <button type="button" class="btn btn-sm btn-secondary btn-page" data-page="next">Next</button>';
                pag.querySelectorAll('.btn-page').forEach(function (b) {
                    b.onclick = function () {
                        if (b.getAttribute('data-page') === 'prev' && studentsPage > 1) studentsPage--;
                        if (b.getAttribute('data-page') === 'next' && studentsPage < totalPages) studentsPage++;
                        loadStudentsList();
                    };
                });
            }
        }).catch(function () {
            document.getElementById('studentsTbody').innerHTML = '<tr><td colspan="4">Failed to load.</td></tr>';
        });
    }

    function openStudentModal(id) {
        loadSectionsForSelect(document.getElementById('studentSection'));
        var title = document.getElementById('modalStudentTitle');
        if (id != null) {
            title.textContent = 'Edit Student';
            api('/api/students/' + id).then(function (st) {
                document.getElementById('studentId').value = st.id;
                document.getElementById('studentSection').value = st.section_id;
                document.getElementById('studentRollNo').value = st.roll_no || '';
                document.getElementById('studentName').value = st.name || '';
            }).catch(function () {
                title.textContent = 'Add Student';
                document.getElementById('studentId').value = '';
            });
        } else {
            title.textContent = 'Add Student';
            document.getElementById('studentId').value = '';
            document.getElementById('studentRollNo').value = '';
            document.getElementById('studentName').value = '';
        }
        document.getElementById('modalStudent').classList.add('show');
    }

    document.getElementById('formStudent').addEventListener('submit', function (e) {
        e.preventDefault();
        var id = document.getElementById('studentId').value;
        var sectionId = parseInt(document.getElementById('studentSection').value, 10);
        var rollNo = document.getElementById('studentRollNo').value.trim();
        var name = document.getElementById('studentName').value.trim();
        if (!rollNo || !name || !sectionId) return;
        var req = id ? api('/api/students/' + id, { method: 'PATCH', body: { section_id: sectionId, roll_no: rollNo, name: name } }) : api('/api/students', { method: 'POST', body: { section_id: sectionId, roll_no: rollNo, name: name } });
        req.then(function () {
            document.getElementById('modalStudent').classList.remove('show');
            toast('Student saved.');
            loadStudentsList();
        }).catch(function (err) {
            toast(err.message, 'error');
        });
    });
    document.querySelector('.btn-cancel-student').onclick = function () { document.getElementById('modalStudent').classList.remove('show'); };
    document.getElementById('modalStudent').onclick = function (e) { if (e.target === this) this.classList.remove('show'); };

    function confirmDeleteStudent(id) {
        document.getElementById('modalConfirmTitle').textContent = 'Delete Student';
        document.getElementById('modalConfirmBody').textContent = 'Delete this student? Attendance records will be removed.';
        document.getElementById('modalConfirm').classList.add('show');
        document.getElementById('btnConfirmOk').onclick = function () {
            api('/api/students/' + id, { method: 'DELETE' }).then(function () {
                document.getElementById('modalConfirm').classList.remove('show');
                toast('Student deleted.');
                loadStudentsList();
            }).catch(function (err) { toast(err.message, 'error'); });
        };
    }

    // ----- Mark Attendance -----
    function renderMarkAttendance() {
        var today = new Date().toISOString().slice(0, 10);
        var wrap = document.getElementById('pageMark');
        wrap.innerHTML = '<div class="page-header"><h2>Mark Attendance</h2><p>Select section, date and session then mark status</p></div>' +
            '<div class="toolbar" id="markToolbar">' +
            '<div class="form-group"><label>Section</label><select id="markSection"><option value="">Select section</option></select></div>' +
            '<div class="form-group"><label>Date</label><input type="date" id="markDate" value="' + today + '"></div>' +
            '<div class="form-group"><label>Session</label><select id="markSession"><option value="morning">Morning</option><option value="afternoon">Afternoon</option></select></div>' +
            '<button type="button" class="btn btn-primary" id="markLoadBtn">Load Students</button>' +
            '</div>' +
            '<div id="markWarning" class="warning-banner" style="display:none"></div>' +
            '<div class="actions-row"><input type="text" class="search-input" id="markSearch" placeholder="Search student"><button type="button" class="btn btn-secondary btn-sm" id="markAllPresent">Select All Present</button><button type="button" class="btn btn-secondary btn-sm" id="markAllAbsent">Select All Absent</button></div>' +
            '<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Roll No</th><th>Name</th><th>Status</th></tr></thead><tbody id="markTbody"></tbody></table></div>' +
            '<div id="markSummary" class="summary-panel" style="display:none"></div>' +
            '<button type="button" class="btn btn-primary" id="markSaveBtn" disabled>Save Attendance</button>';
        loadSectionsForSelect(document.getElementById('markSection'));
        document.getElementById('markLoadBtn').onclick = loadMarkAttendance;
        document.getElementById('markSection').onchange = document.getElementById('markDate').onchange = document.getElementById('markSession').onchange = function () {
            document.getElementById('markSaveBtn').disabled = true;
            document.getElementById('markTbody').innerHTML = '';
            document.getElementById('markSummary').style.display = 'none';
        };
        document.getElementById('markSearch').oninput = filterMarkTable;
        document.getElementById('markAllPresent').onclick = function () { markAttendanceStudents.forEach(function (s) { s.status = 'present'; }); renderMarkTable(); updateMarkSummary(); };
        document.getElementById('markAllAbsent').onclick = function () { markAttendanceStudents.forEach(function (s) { s.status = 'absent'; }); renderMarkTable(); updateMarkSummary(); };
        document.getElementById('markSaveBtn').onclick = saveMarkAttendance;
        document.addEventListener('keydown', function (e) {
            if (e.ctrlKey && e.key === 's') { e.preventDefault(); if (!document.getElementById('markSaveBtn').disabled) saveMarkAttendance(); }
        });
    }

    function loadMarkAttendance() {
        var sectionId = document.getElementById('markSection').value ? parseInt(document.getElementById('markSection').value, 10) : null;
        var dateStr = document.getElementById('markDate').value;
        var session = document.getElementById('markSession').value;
        if (!sectionId || !dateStr) {
            toast('Select section and date.', 'error');
            return;
        }
        currentMarkSectionId = sectionId;
        currentMarkDate = dateStr;
        currentMarkSession = session;
        document.getElementById('markSaveBtn').disabled = true;
        api('/api/attendance?date=' + encodeURIComponent(dateStr) + '&section_id=' + sectionId + '&session=' + encodeURIComponent(session)).then(function (data) {
            markAttendanceStudents = (data.students || []).map(function (s) { return { student_id: s.student_id, roll_no: s.roll_no, name: s.name, status: s.status || 'present' }; });
            markEditingMode = markAttendanceStudents.some(function (s) { return s.status !== 'present'; });
            document.getElementById('markWarning').style.display = markEditingMode ? 'block' : 'none';
            document.getElementById('markWarning').textContent = 'Attendance already marked for this date/session. Editing mode enabled.';
            renderMarkTable();
            updateMarkSummary();
            document.getElementById('markSaveBtn').disabled = false;
        }).catch(function (err) {
            toast(err.message, 'error');
            document.getElementById('markSaveBtn').disabled = false;
        });
    }

    function renderMarkTable() {
        var search = (document.getElementById('markSearch') && document.getElementById('markSearch').value || '').toLowerCase();
        var list = search ? markAttendanceStudents.filter(function (s) {
            return (s.roll_no || '').toLowerCase().indexOf(search) >= 0 || (s.name || '').toLowerCase().indexOf(search) >= 0;
        }) : markAttendanceStudents;
        var tbody = document.getElementById('markTbody');
        tbody.innerHTML = list.map(function (s) {
            var status = s.status || 'present';
            return '<tr data-id="' + s.student_id + '"><td>' + escapeHtml(s.roll_no) + '</td><td>' + escapeHtml(s.name) + '</td><td><button type="button" class="status-toggle ' + status + '" data-id="' + s.student_id + '">' + (status === 'present' ? 'Present' : 'Absent') + '</button></td></tr>';
        }).join('');
        tbody.querySelectorAll('.status-toggle').forEach(function (btn) {
            btn.onclick = function () {
                var id = parseInt(this.getAttribute('data-id'), 10);
                var rec = markAttendanceStudents.find(function (x) { return x.student_id === id; });
                if (rec) {
                    rec.status = rec.status === 'present' ? 'absent' : 'present';
                    this.textContent = rec.status === 'present' ? 'Present' : 'Absent';
                    this.className = 'status-toggle ' + rec.status;
                    updateMarkSummary();
                }
            };
        });
    }

    function filterMarkTable() {
        renderMarkTable();
    }

    function updateMarkSummary() {
        var total = markAttendanceStudents.length;
        var present = markAttendanceStudents.filter(function (s) { return s.status === 'present'; }).length;
        var absent = total - present;
        var sum = document.getElementById('markSummary');
        sum.style.display = total ? 'grid' : 'none';
        sum.innerHTML = '<div class="item">Total <strong>' + total + '</strong></div><div class="item">Present <strong>' + present + '</strong></div><div class="item">Absent <strong>' + absent + '</strong></div>';
    }

    function saveMarkAttendance() {
        if (!currentMarkSectionId || !currentMarkDate || !currentMarkSession) return;
        var absentIds = markAttendanceStudents.filter(function (s) { return s.status === 'absent'; }).map(function (s) { return s.student_id; });
        var btn = document.getElementById('markSaveBtn');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Saving…';
        api('/api/attendance', { method: 'POST', body: { date: currentMarkDate, section_id: currentMarkSectionId, session: currentMarkSession, absent_ids: absentIds } }).then(function () {
            btn.innerHTML = 'Save Attendance';
            btn.disabled = false;
            toast('Attendance saved successfully.');
            loadMarkAttendance();
        }).catch(function (err) {
            btn.innerHTML = 'Save Attendance';
            btn.disabled = false;
            toast(err.message, 'error');
        });
    }

    // ----- Attendance Records -----
    var recordsPage = 1, recordsPerPage = 25, recordsSectionId = null, recordsDate = null, recordsSession = 'morning', recordsSearch = '';

    function renderRecords() {
        var today = new Date().toISOString().slice(0, 10);
        var wrap = document.getElementById('pageRecords');
        wrap.innerHTML = '<div class="page-header"><h2>Attendance Records</h2><p>View and filter attendance</p></div>' +
            '<div class="toolbar"><div class="form-group"><label>Section</label><select id="recordsSection"><option value="">Select section</option></select></div><div class="form-group"><label>Date</label><input type="date" id="recordsDate" value="' + today + '"></div><div class="form-group"><label>Session</label><select id="recordsSession"><option value="morning">Morning</option><option value="afternoon">Afternoon</option></select></div><button type="button" class="btn btn-primary" id="recordsLoadBtn">Load</button></div>' +
            '<div class="actions-row"><input type="text" class="search-input" id="recordsSearch" placeholder="Search"><select id="recordsPerPage"><option value="10">10</option><option value="25" selected>25</option><option value="50">50</option></select></div>' +
            '<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Roll No</th><th>Name</th><th>Status</th></tr></thead><tbody id="recordsTbody"></tbody></table></div>' +
            '<div class="pagination-bar" id="recordsPagination"></div>';
        loadSectionsForSelect(document.getElementById('recordsSection'));
        document.getElementById('recordsLoadBtn').onclick = loadRecords;
        document.getElementById('recordsSection').onchange = document.getElementById('recordsDate').onchange = document.getElementById('recordsSession').onchange = function () { recordsPage = 1; loadRecords(); };
        document.getElementById('recordsSearch').oninput = function () { recordsSearch = this.value; recordsPage = 1; loadRecords(); };
        document.getElementById('recordsPerPage').onchange = function () { recordsPerPage = parseInt(this.value, 10); recordsPage = 1; loadRecords(); };
    }

    function loadRecords() {
        var sectionId = document.getElementById('recordsSection').value ? parseInt(document.getElementById('recordsSection').value, 10) : null;
        var dateStr = document.getElementById('recordsDate').value;
        var session = document.getElementById('recordsSession').value;
        if (!sectionId || !dateStr) {
            document.getElementById('recordsTbody').innerHTML = '<tr><td colspan="3">Select section and date, then click Load.</td></tr>';
            return;
        }
        var q = '?section_id=' + sectionId + '&date=' + encodeURIComponent(dateStr) + '&session=' + encodeURIComponent(session) + '&page=' + recordsPage + '&per_page=' + recordsPerPage;
        if (recordsSearch) q += '&search=' + encodeURIComponent(recordsSearch);
        api('/api/attendance/records' + q).then(function (data) {
            var list = data.records || [];
            var total = data.total || 0;
            var tbody = document.getElementById('recordsTbody');
            tbody.innerHTML = list.map(function (r) {
                return '<tr><td>' + escapeHtml(r.roll_no) + '</td><td>' + escapeHtml(r.name) + '</td><td>' + (r.status === 'absent' ? 'Absent' : 'Present') + '</td></tr>';
            }).join('');
            var totalPages = Math.ceil(total / recordsPerPage) || 1;
            var pag = document.getElementById('recordsPagination');
            pag.innerHTML = 'Total: ' + total;
            if (totalPages > 1) {
                pag.innerHTML += ' <button type="button" class="btn btn-sm btn-secondary btn-page" data-page="prev">Previous</button> Page ' + recordsPage + ' of ' + totalPages + ' <button type="button" class="btn btn-sm btn-secondary btn-page" data-page="next">Next</button>';
                pag.querySelectorAll('.btn-page').forEach(function (b) {
                    b.onclick = function () {
                        if (b.getAttribute('data-page') === 'prev' && recordsPage > 1) recordsPage--;
                        if (b.getAttribute('data-page') === 'next' && recordsPage < totalPages) recordsPage++;
                        loadRecords();
                    };
                });
            }
        }).catch(function () {
            document.getElementById('recordsTbody').innerHTML = '<tr><td colspan="3">Failed to load.</td></tr>';
        });
    }

    // ----- Settings -----
    function renderSettings() {
        document.getElementById('pageSettings').innerHTML = '<div class="page-header"><h2>Settings</h2><p>System settings</p></div><div class="settings-placeholder">Settings panel. Admin-only. No configuration options at this time.</div>';
    }

    // ----- Nav -----
    navItems.forEach(function (n) {
        n.addEventListener('click', function () {
            var page = this.getAttribute('data-page');
            if (page === 'logout') window.location.reload();
            else showPage(page);
        });
    });

    // ----- Chat (Attendance Assistant) -----
    var chatPanel = document.getElementById('chatPanel');
    var chatMessages = document.getElementById('chatMessages');
    var chatInput = document.getElementById('chatInput');
    var chatSendBtn = document.getElementById('chatSendBtn');

    function chatOpen() {
        if (chatPanel) {
            chatPanel.classList.add('open');
            chatPanel.setAttribute('aria-hidden', 'false');
            chatInput.focus();
        }
    }
    function chatClose() {
        if (chatPanel) {
            chatPanel.classList.remove('open');
            chatPanel.setAttribute('aria-hidden', 'true');
        }
    }
    function chatScrollToBottom() {
        if (chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    function formatAiMessage(raw) {
        var s = escapeHtml(raw || '');
        s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        var lines = s.split('\n');
        var out = [];
        var i = 0;
        while (i < lines.length) {
            if (lines[i].match(/^\|.+\|$/)) {
                var tableRows = [];
                while (i < lines.length && lines[i].match(/^\|.+\|$/)) {
                    tableRows.push(lines[i]);
                    i++;
                }
                var skipSep = tableRows.length >= 2 && tableRows[1].replace(/\s/g, '').match(/^\|[\-\:|]+\|$/);
                var tableHtml = '<table class="chat-table">';
                for (var r = 0; r < tableRows.length; r++) {
                    if (skipSep && r === 1) continue;
                    var tag = (r === 0 && skipSep) ? 'th' : 'td';
                    var cells = tableRows[r].split('|').slice(1, -1).map(function (c) { return c.trim(); });
                    tableHtml += '<tr>';
                    for (var c = 0; c < cells.length; c++) {
                        tableHtml += '<' + tag + '>' + cells[c] + '</' + tag + '>';
                    }
                    tableHtml += '</tr>';
                }
                tableHtml += '</table>';
                out.push(tableHtml);
            } else {
                out.push(lines[i]);
                i++;
            }
        }
        s = out.join('\n');
        s = s.replace(/\n/g, '<br>');
        return s;
    }
    function chatAppendMessage(role, text) {
        if (!chatMessages) return;
        var time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        var div = document.createElement('div');
        div.className = 'chat-msg ' + role;
        var body = role === 'ai'
            ? '<span class="chat-msg-body">' + formatAiMessage(text) + '</span>'
            : escapeHtml(text).replace(/\n/g, '<br>');
        div.innerHTML = body + '<span class="chat-msg-time">' + escapeHtml(time) + '</span>';
        chatMessages.appendChild(div);
        chatScrollToBottom();
    }
    function chatShowLoading(show) {
        var el = document.getElementById('chatLoadingEl');
        if (show) {
            if (!el) {
                el = document.createElement('div');
                el.id = 'chatLoadingEl';
                el.className = 'chat-loading chat-loading-dots';
                el.textContent = 'Thinking';
                chatMessages.appendChild(el);
            }
            el.style.display = 'block';
            chatScrollToBottom();
        } else if (el) {
            el.style.display = 'none';
        }
    }
    function chatSend() {
        var q = (chatInput && chatInput.value) ? chatInput.value.trim() : '';
        if (!q) return;
        chatInput.value = '';
        chatAppendMessage('user', q);
        chatShowLoading(true);
        api('/api/chat', { method: 'POST', body: { question: q } })
            .then(function (data) {
                chatShowLoading(false);
                chatAppendMessage('ai', data.response || 'No response.');
            })
            .catch(function (err) {
                chatShowLoading(false);
                var msg = (err && err.message) ? err.message : 'AI usage limit reached. Please try later.';
                if (typeof err === 'object' && err.response) {
                    try { var d = JSON.parse(err.response); if (d.response) msg = d.response; } catch (e) {}
                }
                chatAppendMessage('ai', msg);
            });
    }
    if (document.getElementById('chatFloatingBtn')) {
        document.getElementById('chatFloatingBtn').addEventListener('click', chatOpen);
    }
    if (document.getElementById('chatCloseBtn')) {
        document.getElementById('chatCloseBtn').addEventListener('click', chatClose);
    }
    if (chatSendBtn) {
        chatSendBtn.addEventListener('click', chatSend);
    }
    if (chatInput) {
        chatInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
                chatSend();
            }
        });
    }

    showPage('dashboard');
})();
