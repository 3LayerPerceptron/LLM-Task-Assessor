<?php
require_once('../../config.php');

require_login();
require_sesskey();

$cmid = required_param('cmid', PARAM_INT);

$cm = get_coursemodule_from_id('assign', $cmid, 0, false, MUST_EXIST);
require_capability('mod/assign:grade', context_module::instance($cm->id));

$assignid = $cm->instance;

// Load queue statuses.
$queued = $DB->get_records('local_aigrader_queue', ['assignid' => $assignid]);

// Load results.
$results = $DB->get_records('local_aigrader_result', ['assignid' => $assignid]);

$data = [];

foreach ($queued as $q) {
    $data[$q->userid] = [
        'status'   => $q->status,
        'grade'    => null,
        'feedback' => null,
    ];
}

foreach ($results as $r) {
    if (!isset($data[$r->userid])) {
        $data[$r->userid] = ['status' => 'done'];
    }
    $data[$r->userid]['grade']    = $r->aigrade;
    $data[$r->userid]['feedback'] = $r->aifeedback;
}

header('Content-Type: application/json');
echo json_encode(['success' => true, 'data' => $data]);
