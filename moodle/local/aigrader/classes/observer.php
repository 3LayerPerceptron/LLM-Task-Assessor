<?php
namespace local_aigrader;

defined('MOODLE_INTERNAL') || die();

use core\event\base;
use mod_assign\event\submission_created;
use mod_assign\event\submission_updated;

/**
 * Event observer for AI Grader.
 */
class observer {

    /**
     * Handle submission created.
     *
     * @param submission_created $event
     * @return void
     */
    public static function submission_created(submission_created $event): void {
        self::queue_submission($event);
    }

    /**
     * Handle submission updated.
     *
     * @param submission_updated $event
     * @return void
     */
    public static function submission_updated(submission_updated $event): void {
        self::queue_submission($event);
    }

    /**
     * Put submission into AI queue (if not already there).
     *
     * @param base $event
     * @return void
     */
    protected static function queue_submission(base $event): void {
        global $DB;

        $submissionid = $event->objectid;
        $context = $event->get_context();
        $courseid = $event->courseid;
        $userid = $event->relateduserid ?? $event->userid;

        // Get assign id from context (cm → instance).
        $cm = get_coursemodule_from_id('assign', $context->instanceid, 0, false, MUST_EXIST);
        $assignid = $cm->instance;

        if ($DB->record_exists('local_aigrader_queue', ['submissionid' => $submissionid])) {
            // Update existing record to requeue.
            $record = $DB->get_record('local_aigrader_queue', ['submissionid' => $submissionid], '*', MUST_EXIST);
            $record->status = 'pending';
            $record->retries = 0;
            $record->timemodified = time();
            $record->lastpoll = 0;
            $DB->update_record('local_aigrader_queue', $record);
            return;
        }

        $record = new \stdClass();
        $record->submissionid = $submissionid;
        $record->courseid = $courseid;
        $record->assignid = $assignid;
        $record->userid = $userid;
        $record->status = 'pending';
        $record->externaljobid = null;
        $record->retries = 0;
        $record->timecreated = time();
        $record->timemodified = time();
        $record->lastpoll = 0;

        $DB->insert_record('local_aigrader_queue', $record);
    }
}
