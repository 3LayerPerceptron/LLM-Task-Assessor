<?php
namespace local_aigrader\task;

defined('MOODLE_INTERNAL') || die();

use core\task\scheduled_task;

/**
 * Scheduled task to poll external AI grading service for results
 * or generate mock results in mock mode.
 */
class poll_results extends scheduled_task {

    public function get_name(): string {
        return get_string('task_poll_results', 'local_aigrader');
    }

    public function execute(): void {
        global $DB;

        $mockmode = (int)(get_config('local_aigrader', 'mockmode') ?? 0) === 1;
        $mockdelay = (int)(get_config('local_aigrader', 'mockdelay') ?? 10);

        $endpoint = get_config('local_aigrader', 'endpoint');
        $token = get_config('local_aigrader', 'token');
        $pollinterval = (int)(get_config('local_aigrader', 'pollinterval') ?? 60);
        $maxretries = (int)(get_config('local_aigrader', 'maxretries') ?? 10);

        $now = time();

        mtrace('local_aigrader: mode=' . ($mockmode ? 'mock' : 'real')
            . ' mockdelay=' . $mockdelay . 's'
            . ' pollinterval=' . $pollinterval . 's'
            . ' maxretries=' . $maxretries);

        if (!$mockmode) {
            mtrace('local_aigrader: endpoint=' . ($endpoint ?: '(not set)')
                . ' token=' . ($token ? '(set)' : '(not set)'));
        }

        $params = [
            'pending'    => 'pending',
            'processing' => 'processing',
            'cutoff'     => $now - $pollinterval,
        ];
        $sql = "SELECT *
                  FROM {local_aigrader_queue}
                 WHERE status IN (:pending, :processing)
                   AND (lastpoll = 0 OR lastpoll <= :cutoff)
              ORDER BY timecreated ASC";

        $queueitems = $DB->get_records_sql($sql, $params, 0, 100);

        if (!$queueitems) {
            // Check if there are items being held back by pollinterval.
            $total = $DB->count_records_select(
                'local_aigrader_queue',
                "status IN ('pending','processing')"
            );
            if ($total > 0) {
                mtrace('local_aigrader: ' . $total . ' item(s) in queue but skipped'
                    . ' (polled too recently, pollinterval=' . $pollinterval . 's).');
            } else {
                mtrace('local_aigrader: no items to poll.');
            }
            return;
        }

        mtrace('local_aigrader: found ' . count($queueitems) . ' item(s) to process.');

        foreach ($queueitems as $item) {
            mtrace('local_aigrader: processing queue id=' . $item->id
                . ' submissionid=' . $item->submissionid
                . ' userid=' . $item->userid
                . ' status=' . $item->status
                . ' retries=' . $item->retries);
            try {
                if ($mockmode) {
                    $this->process_mock($item, $mockdelay);
                } else {
                    $this->poll_external($item, (string)$endpoint, (string)$token, $maxretries);
                }
            } catch (\Throwable $e) {
                mtrace('local_aigrader: ERROR for queue id=' . $item->id
                    . ' : ' . $e->getMessage()
                    . ' in ' . $e->getFile() . ':' . $e->getLine());
            }
        }

        mtrace('local_aigrader: done.');
    }

    /**
     * Mock processing: after $mockdelay seconds since timecreated, write a hardcoded result.
     */
    protected function process_mock(\stdClass $item, int $mockdelay): void {
        global $DB;

        $now = time();
        $age = $now - (int)$item->timecreated;

        if ($age < $mockdelay) {
            mtrace('local_aigrader:   mock: waiting for delay'
                . ' (' . $age . 's elapsed, need ' . $mockdelay . 's)'
                . ' -> setting status=processing');
            $item->status = 'processing';
            $item->lastpoll = $now;
            $item->timemodified = $now;
            $DB->update_record('local_aigrader_queue', $item);
            return;
        }

        $grade = 85.0;
        $feedback = "Mock AI feedback: work checked automatically.\n\n- Note 1: example.\n- Note 2: example.\n\nReview before publishing.";

        $payload = json_encode([
            'ready'        => true,
            'grade'        => $grade,
            'feedback'     => $feedback,
            'mock'         => true,
            'generated_at' => $now,
        ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);

        if ($existing = $DB->get_record('local_aigrader_result', ['submissionid' => $item->submissionid])) {
            mtrace('local_aigrader:   mock: updating existing result (id=' . $existing->id . ')'
                . ' grade=' . $grade);
            $existing->aigrade    = $grade;
            $existing->aifeedback = $feedback;
            $existing->rawpayload = $payload;
            $DB->update_record('local_aigrader_result', $existing);
        } else {
            mtrace('local_aigrader:   mock: inserting new result grade=' . $grade);
            $result = (object)[
                'submissionid' => $item->submissionid,
                'courseid'     => $item->courseid,
                'assignid'     => $item->assignid,
                'userid'       => $item->userid,
                'aigrade'      => $grade,
                'aifeedback'   => $feedback,
                'rawpayload'   => $payload,
                'timecreated'  => $now,
            ];
            $DB->insert_record('local_aigrader_result', $result);
        }

        mtrace('local_aigrader:   mock: queue id=' . $item->id . ' -> done');
        $item->status = 'done';
        $item->lastpoll = $now;
        $item->timemodified = $now;
        $DB->update_record('local_aigrader_queue', $item);
    }

    /**
     * External polling (real service).
     */
    protected function poll_external(\stdClass $item, string $endpoint, string $token, int $maxretries): void {
        global $DB;

        $now = time();

        if (empty($endpoint)) {
            mtrace('local_aigrader:   ERROR: endpoint not configured, incrementing retries.');
            $item->retries++;
            $item->status = ($item->retries >= $maxretries) ? 'error' : 'pending';
            $item->lastpoll = $now;
            $item->timemodified = $now;
            $DB->update_record('local_aigrader_queue', $item);
            return;
        }

        $url = rtrim($endpoint, '/') . '/api/aigrades?submissionid=' . urlencode($item->submissionid);
        mtrace('local_aigrader:   GET ' . $url);

        $curl = new \curl();
        $headers = [];
        if (!empty($token)) {
            $headers[] = 'Authorization: Bearer ' . $token;
        }
        $curl->setHeader($headers);

        $response = $curl->get($url);
        $httpcode = $curl->get_info()['http_code'] ?? 0;

        mtrace('local_aigrader:   HTTP ' . $httpcode
            . ' response_len=' . strlen((string)$response));

        $item->lastpoll = $now;
        $item->timemodified = $now;

        if ($httpcode !== 200 || empty($response)) {
            $item->retries++;
            $item->status = ($item->retries >= $maxretries) ? 'error' : 'processing';
            mtrace('local_aigrader:   bad response -> retries=' . $item->retries
                . ' status=' . $item->status);
            $DB->update_record('local_aigrader_queue', $item);
            return;
        }

        $data = json_decode($response, true);
        if (!is_array($data) || empty($data['ready'])) {
            mtrace('local_aigrader:   ready=false -> status=processing');
            $item->status = 'processing';
            $DB->update_record('local_aigrader_queue', $item);
            return;
        }

        $aigrade    = isset($data['grade'])    ? (float)$data['grade']    : null;
        $aifeedback = isset($data['feedback']) ? (string)$data['feedback'] : null;

        mtrace('local_aigrader:   ready=true grade=' . $aigrade);

        if ($existing = $DB->get_record('local_aigrader_result', ['submissionid' => $item->submissionid])) {
            $existing->aigrade    = $aigrade;
            $existing->aifeedback = $aifeedback;
            $existing->rawpayload = $response;
            $DB->update_record('local_aigrader_result', $existing);
        } else {
            $result = (object)[
                'submissionid' => $item->submissionid,
                'courseid'     => $item->courseid,
                'assignid'     => $item->assignid,
                'userid'       => $item->userid,
                'aigrade'      => $aigrade,
                'aifeedback'   => $aifeedback,
                'rawpayload'   => $response,
                'timecreated'  => $now,
            ];
            $DB->insert_record('local_aigrader_result', $result);
        }

        mtrace('local_aigrader:   queue id=' . $item->id . ' -> done');
        $item->status = 'done';
        $DB->update_record('local_aigrader_queue', $item);
    }
}
