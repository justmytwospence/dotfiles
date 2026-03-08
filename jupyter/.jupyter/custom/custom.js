$(Jupyter.events).on('app_initialized.NotebookApp', function() {
    var utils = require('base/js/utils');

    // clean up page elements: header, toolbar, and footer
    $('#header-container').hide();
    $('#maintoolbar').remove();
    $('.end_space').remove();

    // line numbers by default
    Jupyter.Cell.options_default.cm_config.lineNumbers = true;

    Jupyter.keyboard_manager.command_shortcuts.add_shortcut('ctrl-t', {
        help: 'Toggle code cells',
        handler: function(e) {
            $('div.input').toggle();
            return false;
        }
    });

    Jupyter.keyboard_manager.command_shortcuts.add_shortcut('ctrl-r', {
        help: 'Run all cells',
        handler: function(event) {
            Jupyter.notebook.restart_run_all();
            return false;
        }
    });

    Jupyter.keyboard_manager.command_shortcuts.add_shortcut('ctrl-k', {
        help: 'Move cell up',
        handler: function(event) {
            Jupyter.notebook.move_cell_up();
            return false;
        }
    });

    Jupyter.keyboard_manager.command_shortcuts.add_shortcut('ctrl-j', {
        help: 'Move cell down',
        handler: function(event) {
            Jupyter.notebook.move_cell_down();
            return false;
        }
    });

    Jupyter.keyboard_manager.command_shortcuts.add_shortcut('g', {
        help: 'Go to first cell',
        handler: function(event) {
            Jupyter.notebook.select(0);
            Jupyter.notebook.scroll_to_top();
            return false;
        }
    });

    Jupyter.keyboard_manager.command_shortcuts.add_shortcut('shift-g', {
        help: 'Go to last cell',
        handler: function(event) {
            var ncells = Jupyter.notebook.ncells();
            Jupyter.notebook.select(ncells - 1);
            Jupyter.notebook.scroll_to_bottom();
            return false;
        }
    });

    Jupyter.keyboard_manager.command_shortcuts.add_shortcut('n', {
        help: 'Scroll notebook down',
        handler: function(event) {
            Jupyter.notebook.scroll_manager.scroll_some(0.1);
            return false;
        }
    });

    Jupyter.keyboard_manager.command_shortcuts.add_shortcut('p', {
        help: 'Scroll notebook up',
        handler: function(event) {
            Jupyter.notebook.scroll_manager.scroll_some(-0.1);
            return false;
        }
    });

});
