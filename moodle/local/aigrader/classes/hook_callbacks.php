<?php
namespace local_aigrader;

defined('MOODLE_INTERNAL') || die();

class hook_callbacks {

    /**
     * Inject AI grader JS into the footer of the individual assign grader page.
     * The grading table page is handled by extend_settings_navigation in lib.php.
     */
    public static function before_footer(
        \core\hook\output\before_standard_footer_html_generation $hook
    ): void {
        global $PAGE, $CFG;

        // Only on assign module pages.
        if (!$PAGE->cm || $PAGE->cm->modname !== 'assign') {
            return;
        }

        // Only on the individual grader page — the grading table already
        // gets JS via extend_settings_navigation.
        $action = optional_param('action', '', PARAM_ALPHA);
        if ($action !== 'grader') {
            return;
        }

        if (!has_capability('mod/assign:grade', $PAGE->context)) {
            return;
        }

        $jsparams = json_encode([
            'cmid'    => (int)$PAGE->cm->id,
            'wwwroot' => $CFG->wwwroot,
            'sesskey' => sesskey(),
        ]);

        $jsurl = $CFG->wwwroot . '/local/aigrader/js/grading_table.js';

        $html  = '<script>window.localAigraderParams = ' . $jsparams . ';'
               . 'console.log("[aigrader] hook injected params", window.localAigraderParams);</script>' . "\n";
        $html .= '<script src="' . $jsurl . '"></script>' . "\n";

        if (method_exists($hook, 'add_html')) {
            $hook->add_html($html);
        }
    }
}
