<?php
defined('MOODLE_INTERNAL') || die();

if ($hassiteconfig) {
    $settings = new admin_settingpage('local_aigrader', get_string('pluginname', 'local_aigrader'));

    $ADMIN->add('localplugins', $settings);

    $settings->add(new admin_setting_heading(
        'local_aigrader/header',
        get_string('settings_header', 'local_aigrader'),
        html_writer::link(
            new moodle_url('/local/aigrader/report.php'),
            get_string('report_link', 'local_aigrader')
        )
    ));

    $settings->add(new admin_setting_configtext(
        'local_aigrader/endpoint',
        get_string('settings_endpoint', 'local_aigrader'),
        get_string('settings_endpoint_desc', 'local_aigrader'),
        '',
        PARAM_URL
    ));

    $settings->add(new admin_setting_configtext(
        'local_aigrader/token',
        get_string('settings_token', 'local_aigrader'),
        get_string('settings_token_desc', 'local_aigrader'),
        '',
        PARAM_RAW_TRIMMED
    ));

    $settings->add(new admin_setting_configtext(
        'local_aigrader/pollinterval',
        get_string('settings_pollinterval', 'local_aigrader'),
        get_string('settings_pollinterval_desc', 'local_aigrader'),
        60,
        PARAM_INT
    ));

    $settings->add(new admin_setting_configtext(
        'local_aigrader/maxretries',
        get_string('settings_maxretries', 'local_aigrader'),
        get_string('settings_maxretries_desc', 'local_aigrader'),
        10,
        PARAM_INT
    ));

    $settings->add(new admin_setting_configcheckbox(
        'local_aigrader/mockmode',
        get_string('settings_mockmode', 'local_aigrader'),
        get_string('settings_mockmode_desc', 'local_aigrader'),
        1
    ));

    $settings->add(new admin_setting_configtext(
        'local_aigrader/mockdelay',
        get_string('settings_mockdelay', 'local_aigrader'),
        get_string('settings_mockdelay_desc', 'local_aigrader'),
        10,
        PARAM_INT
    ));
}
