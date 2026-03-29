<?php
defined('MOODLE_INTERNAL') || die();

$observers = [
    [
        'eventname'   => '\mod_assign\event\submission_created',
        'callback'    => '\local_aigrader\observer::submission_created',
        'includefile' => '/local/aigrader/classes/observer.php',
        'internal'    => false,
        'priority'    => 9999
    ],
    [
        'eventname'   => '\mod_assign\event\submission_updated',
        'callback'    => '\local_aigrader\observer::submission_updated',
        'includefile' => '/local/aigrader/classes/observer.php',
        'internal'    => false,
        'priority'    => 9999
    ],
];
