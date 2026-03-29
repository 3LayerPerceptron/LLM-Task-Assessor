(function() {
    'use strict';

    var params = window.localAigraderParams;
    if (!params) { return; }

    var href = window.location.href;
    var isGraderPage  = href.indexOf('action=grader')  !== -1;
    var isGradingPage = href.indexOf('action=grading') !== -1;

    if (!isGraderPage && !isGradingPage) { return; }

    function escapeHtml(text) {
        var d = document.createElement('div');
        d.appendChild(document.createTextNode(text || ''));
        return d.innerHTML;
    }

    // ----------------------------------------------------------------
    // Grader page — panels next to grade / feedback fields
    // ----------------------------------------------------------------

    /** Remove previously injected panels so re-renders are clean. */
    function removePanels() {
        ['local-aigrader-grade', 'local-aigrader-feedback'].forEach(function(id) {
            var el = document.getElementById(id);
            if (el) { el.parentNode.removeChild(el); }
        });
    }

    function renderGraderPanel(item) {
        removePanels();

        var gradeRow    = document.getElementById('fitem_id_grade');
        var feedbackRow = document.getElementById('fitem_id_assignfeedbackcomments_editor');

        if (!gradeRow && !feedbackRow) { return; }

        // AI Grade row.
        if (gradeRow) {
            var gradePanel = document.createElement('div');
            gradePanel.id        = 'local-aigrader-grade';
            gradePanel.className = 'mb-3 row fitem';

            var gradeLabel = document.createElement('div');
            gradeLabel.className = 'col-md-3 col-form-label d-flex pb-0 pr-md-0';
            gradeLabel.innerHTML = '<label class="d-inline word-break"><strong>AI Grade</strong></label>';

            var gradeValue = document.createElement('div');
            gradeValue.className = 'col-md-9 felement';

            if (!item) {
                gradeValue.innerHTML = '<span class="text-muted">&mdash; not queued</span>';
            } else if (item.status === 'pending') {
                gradeValue.innerHTML = '<span class="text-warning">&#9679; Pending</span>';
            } else if (item.status === 'processing') {
                gradeValue.innerHTML = '<span class="text-info">&#9679; Processing\u2026</span>';
            } else if (item.status === 'error') {
                gradeValue.innerHTML = '<span class="text-danger">&#9679; AI error</span>';
            } else if (item.grade !== null && item.grade !== undefined) {
                gradeValue.innerHTML = '<strong class="text-primary" style="font-size:1.2em">'
                    + escapeHtml(parseFloat(item.grade).toFixed(1)) + ' / 100</strong>';
            } else {
                gradeValue.innerHTML = '<span class="text-warning">&#9679; Pending</span>';
            }

            gradePanel.appendChild(gradeLabel);
            gradePanel.appendChild(gradeValue);
            gradeRow.parentNode.insertBefore(gradePanel, gradeRow);
        }

        // AI Feedback row.
        if (feedbackRow) {
            var fbPanel = document.createElement('div');
            fbPanel.id        = 'local-aigrader-feedback';
            fbPanel.className = 'mb-3 row fitem';

            var fbLabel = document.createElement('div');
            fbLabel.className = 'col-md-3 col-form-label d-flex pb-0 pr-md-0';
            fbLabel.innerHTML = '<label class="d-inline word-break"><strong>AI Feedback</strong></label>';

            var fbValue = document.createElement('div');
            fbValue.className = 'col-md-9 felement';

            if (item && item.feedback) {
                var pre = document.createElement('pre');
                pre.className    = 'p-2 rounded border bg-light';
                pre.style.cssText = 'white-space:pre-wrap;font-family:inherit;font-size:0.9em;'
                    + 'margin:0;max-height:300px;overflow-y:auto';
                pre.textContent  = item.feedback;
                fbValue.appendChild(pre);
            } else {
                fbValue.innerHTML = '<span class="text-muted">&mdash;</span>';
            }

            fbPanel.appendChild(fbLabel);
            fbPanel.appendChild(fbValue);
            feedbackRow.parentNode.insertBefore(fbPanel, feedbackRow);
        }
    }

    // ----------------------------------------------------------------
    // Grading table page — AI Grade column
    // ----------------------------------------------------------------
    function renderGradingTable(data) {
        var table = document.querySelector('table.generaltable')
            || document.querySelector('#grading-action-form table');
        if (!table) { return; }

        var thead = table.querySelector('thead tr');
        if (thead) {
            var th = document.createElement('th');
            th.className      = 'header c-aigrade';
            th.scope          = 'col';
            th.style.minWidth = '90px';
            th.textContent    = 'AI Grade';
            thead.appendChild(th);
        }

        table.querySelectorAll('tbody tr').forEach(function(row) {
            var td = document.createElement('td');
            td.className = 'cell c-aigrade';

            var userid = null;
            var cb = row.querySelector('input[name="selectedusers"]');
            if (cb) { userid = parseInt(cb.value, 10); }
            if (!userid && row.dataset && row.dataset.userid) {
                userid = parseInt(row.dataset.userid, 10);
            }
            if (!userid) {
                var a = row.querySelector('a[href*="user/view.php"]');
                if (a) { var m = a.href.match(/[?&]id=(\d+)/); if (m) userid = parseInt(m[1], 10); }
            }

            var item = userid ? data[userid] : null;

            if (!item) {
                td.innerHTML = '<span style="color:#999">&mdash;</span>';
            } else if (item.status === 'pending') {
                td.innerHTML = '<span style="color:#e67e22">&#9679; Pending</span>';
            } else if (item.status === 'processing') {
                td.innerHTML = '<span style="color:#2980b9">&#9679; Processing</span>';
            } else if (item.status === 'error') {
                td.innerHTML = '<span style="color:#c0392b">&#9679; Error</span>';
            } else if (item.grade !== null && item.grade !== undefined) {
                var grade = parseFloat(item.grade).toFixed(1);
                var html  = '<strong>' + escapeHtml(grade) + '</strong>';
                if (item.feedback) {
                    var short = item.feedback.length > 80
                        ? item.feedback.substring(0, 80) + '\u2026'
                        : item.feedback;
                    html += '<br><small style="color:#555;font-size:0.8em">' + escapeHtml(short) + '</small>';
                }
                td.innerHTML = html;
            } else {
                td.innerHTML = '<span style="color:#999">&mdash;</span>';
            }

            row.appendChild(td);
        });
    }

    // ----------------------------------------------------------------
    // Fetch AI data for the whole assignment once, cache it.
    // ----------------------------------------------------------------
    var cachedData = null;

    function fetchData(callback) {
        if (cachedData) { callback(cachedData); return; }

        var url = params.wwwroot + '/local/aigrader/ajax.php'
            + '?cmid='    + encodeURIComponent(params.cmid)
            + '&sesskey=' + encodeURIComponent(params.sesskey);

        var xhr = new XMLHttpRequest();
        xhr.open('GET', url);
        xhr.onload = function() {
            if (xhr.status !== 200) { return; }
            try {
                var response = JSON.parse(xhr.responseText);
                if (response && response.success) {
                    cachedData = response.data;
                    callback(cachedData);
                }
            } catch (e) { /* ignore */ }
        };
        xhr.send();
    }

    // ----------------------------------------------------------------
    // Grader page: watch for form (re)renders caused by next/prev nav.
    // Uses a persistent MutationObserver so it fires on every student.
    // ----------------------------------------------------------------
    function startGraderWatcher() {
        var lastUserid = null;

        function getCurrentUserid() {
            var m = window.location.href.match(/[?&]userid=(\d+)/);
            return m ? parseInt(m[1], 10) : null;
        }

        function tryRender() {
            if (!document.getElementById('fitem_id_grade')) { return; }
            // Skip if we already rendered for this userid.
            var uid = getCurrentUserid();
            if (uid === lastUserid) { return; }
            lastUserid = uid;

            fetchData(function(data) {
                var item = uid ? data[uid] : null;
                renderGraderPanel(item);
            });
        }

        // Persistent observer — stays alive for the whole page session.
        var observer = new MutationObserver(tryRender);
        observer.observe(document.body, {childList: true, subtree: true});

        // Also try immediately in case form is already in DOM.
        tryRender();
    }

    // ----------------------------------------------------------------
    // Entry point
    // ----------------------------------------------------------------
    function init() {
        if (isGraderPage) {
            startGraderWatcher();
        } else {
            fetchData(function(data) {
                renderGradingTable(data);
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
