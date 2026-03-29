<?php
defined('MOODLE_INTERNAL') || die();

$hooks = [
    [
        'hook'     => \core\hook\output\before_standard_footer_html_generation::class,
        'callback' => 'local_aigrader\hook_callbacks::before_footer',
        'priority' => 500,
    ],
];
