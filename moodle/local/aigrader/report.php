<?php
require_once('../../config.php');

require_login();

// Optional filter: if opened from an assign page, cmid is passed.
$cmid = optional_param('cmid', 0, PARAM_INT);

if ($cmid) {
    $cm = get_coursemodule_from_id('assign', $cmid, 0, false, MUST_EXIST);
    require_capability('mod/assign:grade', context_module::instance($cm->id));
    $assignid = $cm->instance;
} else {
    require_capability('moodle/site:config', context_system::instance());
    $assignid = 0;
}

// Always use system context for page setup — avoids cm/course mismatch errors.
$PAGE->set_context(context_system::instance());
$PAGE->set_url(new moodle_url('/local/aigrader/report.php', $cmid ? ['cmid' => $cmid] : []));
$PAGE->set_title(get_string('report_title', 'local_aigrader'));
$PAGE->set_heading(get_string('report_title', 'local_aigrader'));
$PAGE->set_pagelayout('admin');

echo $OUTPUT->header();
echo $OUTPUT->heading(get_string('report_title', 'local_aigrader'));

if ($cmid) {
    $backurl = new moodle_url('/mod/assign/view.php', ['id' => $cmid, 'action' => 'grading']);
    echo html_writer::tag('p',
        html_writer::link($backurl, '&larr; ' . get_string('back'))
    );
}

// --- Queue table ---
echo html_writer::tag('h3', get_string('report_queue', 'local_aigrader'));

$where  = $assignid ? 'WHERE q.assignid = :assignid' : '';
$params = $assignid ? ['assignid' => $assignid] : [];

$queuerows = $DB->get_records_sql(
    "SELECT q.*, " . $DB->sql_fullname('u.firstname', 'u.lastname') . " AS fullname,
            c.fullname AS coursename, a.name AS assignname
       FROM {local_aigrader_queue} q
       JOIN {user} u   ON u.id = q.userid
       JOIN {course} c ON c.id = q.courseid
       JOIN {assign} a ON a.id = q.assignid
       $where
   ORDER BY q.timecreated DESC",
    $params, 0, 200
);

if ($queuerows) {
    $table = new html_table();
    $table->head = [
        'ID',
        get_string('report_col_user', 'local_aigrader'),
        get_string('report_col_course', 'local_aigrader'),
        get_string('report_col_assign', 'local_aigrader'),
        get_string('report_col_submission', 'local_aigrader'),
        get_string('report_col_status', 'local_aigrader'),
        get_string('report_col_retries', 'local_aigrader'),
        get_string('report_col_created', 'local_aigrader'),
        get_string('report_col_lastpoll', 'local_aigrader'),
    ];
    $table->attributes['class'] = 'admintable generaltable';

    $statusmap = [
        'pending'    => get_string('status_pending', 'local_aigrader'),
        'processing' => get_string('status_processing', 'local_aigrader'),
        'done'       => get_string('status_done', 'local_aigrader'),
        'error'      => get_string('status_error', 'local_aigrader'),
    ];

    foreach ($queuerows as $row) {
        $table->data[] = [
            $row->id,
            s($row->fullname),
            s($row->coursename),
            s($row->assignname),
            $row->submissionid,
            $statusmap[$row->status] ?? $row->status,
            $row->retries,
            userdate($row->timecreated),
            $row->lastpoll ? userdate($row->lastpoll) : '-',
        ];
    }
    echo html_writer::table($table);
} else {
    echo html_writer::tag('p', get_string('report_queue_empty', 'local_aigrader'));
}

// --- Results table ---
echo html_writer::tag('h3', get_string('report_results', 'local_aigrader'));

$where  = $assignid ? 'WHERE r.assignid = :assignid' : '';
$params = $assignid ? ['assignid' => $assignid] : [];

$resultrows = $DB->get_records_sql(
    "SELECT r.*, " . $DB->sql_fullname('u.firstname', 'u.lastname') . " AS fullname,
            c.fullname AS coursename, a.name AS assignname
       FROM {local_aigrader_result} r
       JOIN {user} u   ON u.id = r.userid
       JOIN {course} c ON c.id = r.courseid
       JOIN {assign} a ON a.id = r.assignid
       $where
   ORDER BY r.timecreated DESC",
    $params, 0, 200
);

if ($resultrows) {
    $table = new html_table();
    $table->head = [
        'ID',
        get_string('report_col_user', 'local_aigrader'),
        get_string('report_col_course', 'local_aigrader'),
        get_string('report_col_assign', 'local_aigrader'),
        get_string('report_col_submission', 'local_aigrader'),
        get_string('report_col_grade', 'local_aigrader'),
        get_string('report_col_feedback', 'local_aigrader'),
        get_string('report_col_created', 'local_aigrader'),
    ];
    $table->attributes['class'] = 'admintable generaltable';

    foreach ($resultrows as $row) {
        $table->data[] = [
            $row->id,
            s($row->fullname),
            s($row->coursename),
            s($row->assignname),
            $row->submissionid,
            $row->aigrade !== null ? format_float($row->aigrade, 2) : '-',
            html_writer::tag('pre', s($row->aifeedback),
                ['style' => 'white-space:pre-wrap;max-width:400px;font-size:0.85em;margin:0']),
            userdate($row->timecreated),
        ];
    }
    echo html_writer::table($table);
} else {
    echo html_writer::tag('p', get_string('report_results_empty', 'local_aigrader'));
}

echo $OUTPUT->footer();
