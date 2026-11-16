from shiny import App, reactive, render, ui

from shared import FILTERS, filter_choices, search

# one multi-select dropdown per filter
filter_inputs = [
    ui.input_selectize(fid, label, choices=filter_choices(column), multiple=True)
    for fid, (label, column) in FILTERS.items()
]

app_ui = ui.page_sidebar(
    ui.sidebar(*filter_inputs, title="Filters"),
    ui.input_text("query", "Search", placeholder="e.g. muscle atrophy in mice", width="100%"),
    ui.input_action_button("go", "Search"),
    ui.output_data_frame("results"),
    title="OSDR study search",
)


def server(input, output, session):
    @render.data_frame
    @reactive.event(input.go)
    def results():
        filters = {column: input[fid]() for fid, (label, column) in FILTERS.items()}
        df = search(input.query(), filters)
        return render.DataGrid(
            df,
            width="100%",  # use the full page width
            height="70vh",
            styles=[
                {"cols": [0], "style": {"min-width": "90px"}},                         # Accession
                {"cols": [1], "style": {"min-width": "250px", "max-width": "350px"}},  # Study Title
                {"cols": [2], "style": {"min-width": "400px", "max-width": "600px"}},  # Study Description
                {"cols": [3], "style": {"max-width": "180px"}},                        # organism
            ],
        )


app = App(app_ui, server)
