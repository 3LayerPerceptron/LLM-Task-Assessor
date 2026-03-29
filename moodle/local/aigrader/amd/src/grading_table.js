/**
 * Injects AI grade column into the assign grading table.
 */
define(['jquery'], function($) {

    function init(params) {
        var cmid = params.cmid;

        // Only run on the grading table page (action=grading).
        if (window.location.href.indexOf('action=grading') === -1) {
            return;
        }

        $.ajax({
            url: M.cfg.wwwroot + '/local/aigrader/ajax.php',
            data: {cmid: cmid, sesskey: M.cfg.sesskey},
            dataType: 'json',
            success: function(response) {
                if (response && response.success) {
                    renderColumn(response.data);
                }
            }
        });
    }

    function renderColumn(data) {
        var table = $('table.generaltable');
        if (!table.length) {
            return;
        }

        // Add header cell.
        table.find('thead tr').first().append(
            '<th class="header c-aigrade" scope="col" style="min-width:90px">AI Grade</th>'
        );

        // Add a cell to each student row.
        table.find('tbody tr').each(function() {
            var checkbox = $(this).find('input[name="selectedusers"]');
            if (!checkbox.length) {
                $(this).append('<td class="cell c-aigrade"></td>');
                return;
            }

            var userid = parseInt(checkbox.val(), 10);
            var item   = data[userid];
            var cell   = '';

            if (!item) {
                cell = '<span style="color:#999">—</span>';
            } else if (item.status === 'pending') {
                cell = '<span style="color:#e67e22" title="Queued for AI grading">&#9679; Pending</span>';
            } else if (item.status === 'processing') {
                cell = '<span style="color:#2980b9" title="AI is grading">&#9679; Processing</span>';
            } else if (item.status === 'error') {
                cell = '<span style="color:#c0392b" title="AI grading failed">&#9679; Error</span>';
            } else if (item.status === 'done' && item.grade !== null) {
                var grade    = parseFloat(item.grade).toFixed(1);
                var feedback = item.feedback ? escapeHtml(item.feedback).replace(/\n/g, '<br>') : '';
                cell = '<strong>' + grade + '</strong>';
                if (feedback) {
                    var short = feedback.length > 80
                        ? feedback.substring(0, 80) + '…'
                        : feedback;
                    cell += '<br><small style="color:#555;font-size:0.8em">' + short + '</small>';
                }
            } else {
                cell = '<span style="color:#999">—</span>';
            }

            $(this).append('<td class="cell c-aigrade">' + cell + '</td>');
        });
    }

    function escapeHtml(text) {
        return $('<div>').text(text).html();
    }

    return {init: init};
});
