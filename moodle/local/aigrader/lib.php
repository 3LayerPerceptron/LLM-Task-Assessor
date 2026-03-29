<?php
defined('MOODLE_INTERNAL') || die();

/**
 * Called by Moodle on every page before the top of the body HTML is output.
 * Used to inject the AI grader JS on assign pages.
 *
 * @return string HTML to inject at top of body.
 */
function local_aigrader_before_standard_top_of_body_html(): string {
    global $PAGE, $CFG;

    if (!$PAGE->cm || $PAGE->cm->modname !== 'assign') {
        return '';
    }

    $action = optional_param('action', '', PARAM_ALPHA);
    if (!in_array($action, ['grader', 'grading'])) {
        return '';
    }

    if (!has_capability('mod/assign:grade', $PAGE->context)) {
        return '';
    }

    $jsparams = json_encode([
        'cmid'    => (int)$PAGE->cm->id,
        'wwwroot' => $CFG->wwwroot,
        'sesskey' => sesskey(),
    ]);

    $jsurl = $CFG->wwwroot . '/local/aigrader/js/grading_table.js';

    return '<script>window.localAigraderParams = ' . $jsparams . ';'
         . 'console.log("[aigrader] params injected via before_standard_top_of_body_html");</script>' . "\n"
         . '<script src="' . $jsurl . '"></script>' . "\n";
}

/**
 * Adds "AI Grader report" link to the assignment settings navigation.
 */
function local_aigrader_extend_settings_navigation($settingsnav, $context): void {
    global $PAGE;

    if (!$PAGE->cm || $PAGE->cm->modname !== 'assign') {
        return;
    }

    if (!has_capability('mod/assign:grade', $context)) {
        return;
    }

    $node = $settingsnav->find('modulesettings', navigation_node::TYPE_SETTING);
    if ($node) {
        $url = new moodle_url('/local/aigrader/report.php', ['cmid' => $PAGE->cm->id]);
        $node->add(
            get_string('report_link', 'local_aigrader'),
            $url,
            navigation_node::TYPE_SETTING,
            null,
            'local_aigrader_report',
            new pix_icon('i/grades', '')
        );
    }
}
