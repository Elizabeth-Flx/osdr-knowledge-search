from shiny import App, reactive, render, ui

from shared import search

app_ui = ui.page_fluid(
    ui.h2("OSDR study search"),
    ui.input_text("query", "Search", placeholder="e.g. muscle atrophy in mice", width="100%"),
    ui.input_action_button("go", "Search"),
    ui.output_data_frame("results"),
)


def server(input, output, session):
    @render.data_frame
    @reactive.event(input.go)
    def results():
        return search(input.query())


app = App(app_ui, server)
