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
        var sidebar = document.getElementById('sidebar');
        var backdrop = document.getElementById('sidebarBackdrop');
        var toggle = document.getElementById('sidebarToggle');
        if (sidebar && sidebar.classList.contains('closed') === false && window.matchMedia('(max-width: 768px)').matches) {
            sidebar.classList.add('closed');
            if (backdrop) { backdrop.classList.remove('visible'); backdrop.setAttribute('aria-hidden', 'true'); }
            if (toggle) toggle.setAttribute('aria-expanded', 'false');
        }
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
        else if (pageId === 'logout') openLogoutModal();
    }

    function toast(message, type) {
        type = type || 'success';
        var el = document.createElement('div');
        el.className = 'toast ' + type;
        el.setAttribute('role', type === 'error' ? 'alert' : 'status');
        el.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');
        el.textContent = message;
        toastContainer.appendChild(el);
        setTimeout(function () {
            if (el.parentNode) el.parentNode.removeChild(el);
        }, type === 'error' ? 5000 : 3500);
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

    var lastFocusedBeforeModal = null;

    function getFocusables(container) {
        var sel = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
        return Array.prototype.filter.call(container.querySelectorAll(sel), function (el) {
            return !el.disabled && el.offsetParent !== null;
        });
    }

    function trapFocus(modalEl) {
        var focusables = getFocusables(modalEl);
        if (focusables.length === 0) return;
        focusables[0].focus();
        modalEl.addEventListener('keydown', function onKey(e) {
            if (e.key !== 'Tab') return;
            var first = focusables[0];
            var last = focusables[focusables.length - 1];
            if (e.shiftKey) {
                if (document.activeElement === first) { e.preventDefault(); last.focus(); }
            } else {
                if (document.activeElement === last) { e.preventDefault(); first.focus(); }
            }
        });
    }

    function openModal(modalId, firstFocusSelector) {
        var modal = document.getElementById(modalId);
        if (!modal) return;
        lastFocusedBeforeModal = document.activeElement;
        modal.setAttribute('aria-hidden', 'false');
        modal.classList.add('show');
        var first = firstFocusSelector ? modal.querySelector(firstFocusSelector) : null;
        var focusables = getFocusables(modal);
        if (first) first.focus();
        else if (focusables.length) focusables[0].focus();
        modal.addEventListener('keydown', function onEsc(e) {
            if (e.key === 'Escape') { closeModal(modalId); modal.removeEventListener('keydown', onEsc); }
        });
    }

    function closeModal(modalId) {
        var modal = document.getElementById(modalId);
        if (!modal) return;
        modal.setAttribute('aria-hidden', 'true');
        modal.classList.remove('show');
        if (lastFocusedBeforeModal && typeof lastFocusedBeforeModal.focus === 'function') lastFocusedBeforeModal.focus();
    }

    // ----- Dashboard -----
    var dashboardSkeletonHtml = '<div class="summary-card skeleton-card"><div class="skeleton skeleton-line"></div><div class="skeleton skeleton-value"></div></div>' +
        '<div class="summary-card skeleton-card"><div class="skeleton skeleton-line"></div><div class="skeleton skeleton-value"></div></div>' +
        '<div class="summary-card skeleton-card"><div class="skeleton skeleton-line"></div><div class="skeleton skeleton-value"></div></div>' +
        '<div class="summary-card skeleton-card"><div class="skeleton skeleton-line"></div><div class="skeleton skeleton-value"></div></div>';

    function renderDashboard() {
        var wrap = document.getElementById('pageDashboard');
        wrap.innerHTML = '<div class="page-header"><h2>Dashboard</h2><p>Overview of sections, students, and today’s attendance</p></div><div class="cards-grid" id="dashboardCards">' + dashboardSkeletonHtml + '</div>';
        api('/api/dashboard/stats').then(function (data) {
            document.getElementById('dashboardCards').innerHTML =
                '<div class="summary-card"><div class="card-label">Total Sections</div><div class="card-value">' + (data.total_sections || 0) + '</div></div>' +
                '<div class="summary-card"><div class="card-label">Total Students</div><div class="card-value">' + (data.total_students || 0) + '</div></div>' +
                '<div class="summary-card"><div class="card-label">Attendance Marked Today</div><div class="card-value">' + (data.attendance_marked_today || 0) + '</div></div>' +
                '<div class="summary-card"><div class="card-label">Total Absentees Today</div><div class="card-value">' + (data.absent_today || 0) + '</div></div>';
        }).catch(function () {
            document.getElementById('dashboardCards').innerHTML = '<div class="empty-state">Unable to load stats. Check your connection and try again.</div>';
        });
    }

    // ----- Sections -----
    var sectionsSkeletonHtml = '<div class="section-card skeleton-card"><div class="skeleton skeleton-line"></div><div class="skeleton skeleton-line short"></div><div class="skeleton skeleton-line" style="width:40%"></div></div>' +
        '<div class="section-card skeleton-card"><div class="skeleton skeleton-line"></div><div class="skeleton skeleton-line short"></div><div class="skeleton skeleton-line" style="width:40%"></div></div>' +
        '<div class="section-card skeleton-card"><div class="skeleton skeleton-line"></div><div class="skeleton skeleton-line short"></div><div class="skeleton skeleton-line" style="width:40%"></div></div>';

    function renderSections() {
        var wrap = document.getElementById('pageSections');
        wrap.innerHTML = '<div class="page-header"><h2>Sections</h2><p>Manage class sections and groups</p></div><div class="actions-row"><button type="button" class="btn btn-primary" id="btnAddSection">+ Add Section</button></div><div class="section-cards" id="sectionCards">' + sectionsSkeletonHtml + '</div>';
        api('/api/sections?stats=1').then(function (list) {
            sectionsCache = list || [];
            var cards = document.getElementById('sectionCards');
            if (sectionsCache.length === 0) {
                cards.innerHTML = '<div class="empty-state"><p>No sections yet. Add your first section to start managing students and attendance.</p><button type="button" class="btn btn-primary" id="emptyAddSection">+ Add Section</button></div>';
                document.getElementById('emptyAddSection').onclick = function () { openSectionModal(null); };
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
            document.getElementById('sectionCards').innerHTML = '<div class="empty-state">Could not load sections. Try again or check your connection.</div>';
        });
        var btnAdd = document.getElementById('btnAddSection');
        if (btnAdd) btnAdd.onclick = function () { openSectionModal(null); };
    }

    function openSectionModal(id) {
        var errEl = document.getElementById('sectionNameError');
        if (errEl) errEl.textContent = '';
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
        openModal('modalSection', '#sectionName');
    }

    function closeSectionModal() {
        closeModal('modalSection');
    }

    document.getElementById('formSection').addEventListener('submit', function (e) {
        e.preventDefault();
        var nameInput = document.getElementById('sectionName');
        var name = nameInput.value.trim();
        var errEl = document.getElementById('sectionNameError');
        if (errEl) errEl.textContent = '';
        if (!name) return;
        var id = this.dataset.editId;
        var req = id ? api('/api/sections/' + id, { method: 'PATCH', body: { name: name } }) : api('/api/sections', { method: 'POST', body: { name: name } });
        req.then(function () {
            closeSectionModal();
            toast('Section saved.');
            renderSections();
        }).catch(function (err) {
            var msg = err && err.message ? err.message : 'Could not save section.';
            if (errEl) { errEl.textContent = msg; errEl.setAttribute('role', 'alert'); }
            toast(msg, 'error');
        });
    });
    document.querySelector('.btn-cancel-section').onclick = closeSectionModal;
    document.getElementById('modalSection').onclick = function (e) { if (e.target === this) closeSectionModal(); };

    function confirmDeleteSection(id) {
        var s = sectionsCache.find(function (x) { return x.id === id; });
        document.getElementById('modalConfirmTitle').textContent = 'Delete Section';
        document.getElementById('modalConfirmBody').textContent = 'Delete section "' + (s ? s.name : '') + '"? All students and attendance in this section will be removed.';
        openModal('modalConfirm', '#btnConfirmCancel');
        document.getElementById('btnConfirmOk').onclick = function () {
            api('/api/sections/' + id, { method: 'DELETE' }).then(function () {
                closeModal('modalConfirm');
                toast('Section deleted.');
                renderSections();
            }).catch(function (err) {
                toast(err.message, 'error');
            });
        };
    }

    document.getElementById('btnConfirmCancel').onclick = function () { closeModal('modalConfirm'); };
    document.getElementById('modalConfirm').onclick = function (e) { if (e.target === this) closeModal('modalConfirm'); };

    // ----- Students -----
    var studentsPage = 1, studentsPerPage = 25, studentsTotal = 0, studentsSectionId = null, studentsSearch = '', studentsSortBy = 'roll_no';

    function renderStudents() {
        var wrap = document.getElementById('pageStudents');
        var skeletonRows = Array(5).join('<tr><td><span class="skeleton skeleton-line" style="display:block;width:60px;height:14px"></span></td><td><span class="skeleton skeleton-line" style="display:block;width:120px;height:14px"></span></td><td><span class="skeleton skeleton-line" style="display:block;width:80px;height:14px"></span></td><td></td></tr>');
        wrap.innerHTML = '<div class="page-header"><h2>Students</h2><p>Manage students by section</p></div>' +
            '<div class="actions-row"><input type="text" class="search-input" id="studentsSearch" placeholder="Search roll or name"><select id="studentsSectionFilter"><option value="">All sections</option></select><select id="studentsPerPage"><option value="10">10 per page</option><option value="25" selected>25 per page</option><option value="50">50 per page</option></select><button type="button" class="btn btn-primary" id="btnAddStudent">+ Add Student</button></div>' +
            '<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Roll No <button type="button" class="btn btn-sm btn-secondary sort-btn" data-sort="roll_no">↕</button></th><th>Name <button type="button" class="btn btn-sm btn-secondary sort-btn" data-sort="name">↕</button></th><th>Section</th><th></th></tr></thead><tbody id="studentsTbody">' + skeletonRows + '</tbody></table></div>' +
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
            if (list.length === 0 && !studentsSearch && !studentsSectionId) {
                tbody.innerHTML = '<tr><td colspan="4"><div class="empty-state"><p>No students yet. Add your first student to get started.</p><button type="button" class="btn btn-primary empty-add-student">+ Add Student</button></div></td></tr>';
                var emptyBtn = tbody.querySelector('.empty-add-student');
                if (emptyBtn) emptyBtn.onclick = function () { openStudentModal(null); };
            } else {
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
            }
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
            document.getElementById('studentsTbody').innerHTML = '<tr><td colspan="4"><div class="empty-state">Could not load students. Try again.</div></td></tr>';
        });
    }

    function openStudentModal(id) {
        var errEl = document.getElementById('studentFormError');
        if (errEl) errEl.textContent = '';
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
        openModal('modalStudent', '#studentSection');
    }

    document.getElementById('formStudent').addEventListener('submit', function (e) {
        e.preventDefault();
        var errEl = document.getElementById('studentFormError');
        if (errEl) errEl.textContent = '';
        var id = document.getElementById('studentId').value;
        var sectionId = parseInt(document.getElementById('studentSection').value, 10);
        var rollNo = document.getElementById('studentRollNo').value.trim();
        var name = document.getElementById('studentName').value.trim();
        if (!rollNo || !name || !sectionId) return;
        var req = id ? api('/api/students/' + id, { method: 'PATCH', body: { section_id: sectionId, roll_no: rollNo, name: name } }) : api('/api/students', { method: 'POST', body: { section_id: sectionId, roll_no: rollNo, name: name } });
        req.then(function () {
            closeModal('modalStudent');
            toast('Student saved.');
            loadStudentsList();
        }).catch(function (err) {
            var msg = err && err.message ? err.message : 'Could not save student.';
            if (errEl) { errEl.textContent = msg; errEl.setAttribute('role', 'alert'); }
            toast(msg, 'error');
        });
    });
    document.querySelector('.btn-cancel-student').onclick = function () { closeModal('modalStudent'); };
    document.getElementById('modalStudent').onclick = function (e) { if (e.target === this) closeModal('modalStudent'); };

    function confirmDeleteStudent(id) {
        document.getElementById('modalConfirmTitle').textContent = 'Delete Student';
        document.getElementById('modalConfirmBody').textContent = 'Delete this student? Attendance records will be removed.';
        openModal('modalConfirm', '#btnConfirmCancel');
        document.getElementById('btnConfirmOk').onclick = function () {
            api('/api/students/' + id, { method: 'DELETE' }).then(function () {
                closeModal('modalConfirm');
                toast('Student deleted.');
                loadStudentsList();
            }).catch(function (err) { toast(err.message, 'error'); });
        };
    }

    // ----- Mark Attendance -----
    function renderMarkAttendance() {
        var today = new Date().toISOString().slice(0, 10);
        var defaultSession = typeof getDefaultSession === 'function' ? getDefaultSession() : 'morning';
        var wrap = document.getElementById('pageMark');
        wrap.innerHTML = '<div class="page-header"><h2>Mark Attendance</h2><p>Select section, date and session then mark status</p></div>' +
            '<div class="toolbar" id="markToolbar">' +
            '<div class="form-group"><label>Section</label><select id="markSection"><option value="">Select section</option></select></div>' +
            '<div class="form-group"><label>Date</label><input type="date" id="markDate" value="' + today + '"></div>' +
            '<div class="form-group"><label>Session</label><select id="markSession"><option value="morning"' + (defaultSession === 'morning' ? ' selected' : '') + '>Morning</option><option value="afternoon"' + (defaultSession === 'afternoon' ? ' selected' : '') + '>Afternoon</option></select></div>' +
            '<button type="button" class="btn btn-primary" id="markLoadBtn">Load Students</button>' +
            '</div>' +
            '<div id="markWarning" class="warning-banner" style="display:none"></div>' +
            '<div class="actions-row"><input type="text" class="search-input" id="markSearch" placeholder="Search student"><button type="button" class="btn btn-secondary btn-sm" id="markAllPresent">Select All Present</button><button type="button" class="btn btn-secondary btn-sm" id="markAllAbsent">Select All Absent</button></div>' +
            '<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Roll No</th><th>Name</th><th>Status</th></tr></thead><tbody id="markTbody"></tbody></table></div>' +
            '<div id="markSummary" class="summary-panel" style="display:none"></div>' +
            '<div class="actions-row" style="align-items:center;margin-top:16px"><button type="button" class="btn btn-primary" id="markSaveBtn" disabled>Save Attendance</button><span class="keyboard-hint" id="markSaveHint">Ctrl+S when ready</span></div>';
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
            document.getElementById('recordsTbody').innerHTML = '<tr><td colspan="3"><div class="empty-state"><p>Choose a section and date above, then click <strong>Load</strong> to view attendance records.</p></div></td></tr>';
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
    var APP_VERSION = '1.0';

    function getDefaultSession() {
        try { return localStorage.getItem('attendance_default_session') || 'morning'; } catch (e) { return 'morning'; }
    }
    function setDefaultSession(val) {
        try { localStorage.setItem('attendance_default_session', val); } catch (e) {}
    }

    function getReportEmail() {
        try { return (localStorage.getItem('attendance_report_email') || '').trim(); } catch (e) { return ''; }
    }
    function setReportEmail(val) {
        try { localStorage.setItem('attendance_report_email', (val || '').trim()); } catch (e) {}
    }

    function renderSettings() {
        var defaultSession = getDefaultSession();
        var reportEmail = getReportEmail();
        document.getElementById('pageSettings').innerHTML =
            '<div class="page-header"><h2>Settings</h2><p>Preferences and system info</p></div>' +
            '<div class="settings-card">' +
            '<h3 class="settings-heading">About</h3>' +
            '<p class="settings-about"><strong>AI Attendance</strong> — Admin Dashboard</p>' +
            '<p class="settings-muted">Version ' + APP_VERSION + '. Manage sections, students, and mark attendance with AI-powered chat assistance.</p>' +
            '</div>' +
            '<div class="settings-card">' +
            '<h3 class="settings-heading">Preferences</h3>' +
            '<div class="form-group"><label for="settingsDefaultSession">Default session (Mark Attendance)</label><select id="settingsDefaultSession"><option value="morning"' + (defaultSession === 'morning' ? ' selected' : '') + '>Morning</option><option value="afternoon"' + (defaultSession === 'afternoon' ? ' selected' : '') + '>Afternoon</option></select><p class="settings-muted">Pre-fill the session when you open Mark Attendance.</p></div>' +
            '<div class="form-group"><label for="settingsReportEmail">Report recipient email</label><input type="email" id="settingsReportEmail" placeholder="e.g. admin@school.edu" value="' + escapeHtml(reportEmail) + '"><p class="settings-muted">When you ask the AI to &quot;send absentees to my email&quot; or &quot;email last 3 days absentees&quot;, the report will be sent to this address. The AI will ask for section and session (morning/afternoon) if not specified.</p></div>' +
            '</div>';
        document.getElementById('settingsDefaultSession').onchange = function () {
            setDefaultSession(this.value);
            toast('Default session saved.');
        };
        document.getElementById('settingsReportEmail').onchange = function () {
            setReportEmail(this.value);
            toast('Report email saved.');
        };
        document.getElementById('settingsReportEmail').onblur = function () {
            setReportEmail(this.value);
        };
    }

    function openLogoutModal() {
        openModal('modalLogout', '#btnLogoutCancel');
    }
    document.getElementById('btnLogoutCancel').onclick = function () { closeModal('modalLogout'); };
    document.getElementById('btnLogoutConfirm').onclick = function () { closeModal('modalLogout'); window.location.reload(); };
    document.getElementById('modalLogout').onclick = function (e) { if (e.target === this) closeModal('modalLogout'); };

    // ----- Nav -----
    navItems.forEach(function (n) {
        n.addEventListener('click', function () {
            var page = this.getAttribute('data-page');
            showPage(page);
        });
    });

    // ----- Sidebar mobile toggle -----
    (function () {
        var sidebar = document.getElementById('sidebar');
        var toggle = document.getElementById('sidebarToggle');
        var backdrop = document.getElementById('sidebarBackdrop');
        function openSidebar() {
            sidebar.classList.remove('closed');
            if (backdrop) { backdrop.classList.add('visible'); backdrop.setAttribute('aria-hidden', 'false'); }
            if (toggle) toggle.setAttribute('aria-expanded', 'true');
        }
        function closeSidebar() {
            sidebar.classList.add('closed');
            if (backdrop) { backdrop.classList.remove('visible'); backdrop.setAttribute('aria-hidden', 'true'); }
            if (toggle) toggle.setAttribute('aria-expanded', 'false');
        }
        if (toggle) {
            toggle.addEventListener('click', function () {
                if (sidebar.classList.contains('closed')) openSidebar(); else closeSidebar();
            });
        }
        if (backdrop) backdrop.addEventListener('click', closeSidebar);
        if (window.matchMedia('(max-width: 768px)').matches) sidebar.classList.add('closed');
    })();

    // ----- Chat (Attendance Assistant) -----
    var chatPanel = document.getElementById('chatPanel');
    var chatMessages = document.getElementById('chatMessages');
    var chatInput = document.getElementById('chatInput');
    var chatSendBtn = document.getElementById('chatSendBtn');

    function chatOpen() {
        if (chatPanel) {
            chatPanel.classList.add('open');
            chatPanel.setAttribute('aria-hidden', 'false');
            setTimeout(function () { if (chatInput) chatInput.focus(); }, 100);
        }
    }
    function chatHideWelcome() {
        var w = document.getElementById('chatWelcome');
        if (w) w.classList.add('hidden');
    }
    function chatShowWelcome() {
        var w = document.getElementById('chatWelcome');
        if (w) w.classList.remove('hidden');
    }
    function chatClose() {
        if (chatPanel) {
            chatPanel.classList.remove('open');
            chatPanel.setAttribute('aria-hidden', 'true');
            var btn = document.getElementById('chatFloatingBtn');
            if (btn) setTimeout(function () { btn.focus(); }, 50);
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
        chatHideWelcome();
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
        var reportEmail = getReportEmail();
        api('/api/chat', { method: 'POST', body: { question: q, report_email: reportEmail || undefined } })
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
    document.querySelectorAll('.chat-chip').forEach(function (chip) {
        chip.addEventListener('click', function () {
            var msg = this.getAttribute('data-msg');
            if (msg && chatInput) {
                chatInput.value = msg;
                chatSend();
            }
        });
    });

    showPage('dashboard');
})();
