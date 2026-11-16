import pandas as pd
from shiny import App, reactive, render, ui

from shared import FILTERS, filter_choices, search

# one multi-select dropdown per filter
filter_inputs = [
    ui.input_selectize(fid, label, choices=filter_choices(column), multiple=True)
    for fid, (label, column) in FILTERS.items()
]

# columns shown in the table, everything else is only in the details panel
TABLE_COLUMNS = ["Accession", "Study Title", "organism", "project_type", "score"]

# fields shown in the details panel: label -> column
DETAIL_FIELDS = {
    "Organism": "organism", "Project type": "project_type", "Material": "material",
    "Assay": "assay", "Factors": "factors", "Space agency": "space agency",
    "Flight platform": "flight platform", "Missions": "missions", "Release date": "release date",
}

app_ui = ui.page_sidebar(
    ui.sidebar(*filter_inputs, title="Filters"),
    ui.input_text("query", "Search", placeholder="e.g. muscle atrophy in mice", width="100%"),
    ui.input_radio_buttons("mode", None, {"hybrid": "Hybrid", "semantic": "Semantic", "keyword": "Keyword"},
                           inline=True),
    ui.input_action_button("go", "Search"),
    ui.layout_columns(
        ui.output_data_frame("results"),
        ui.output_ui("details"),
        col_widths=[7, 5],  # table left, details right
    ),
    title="OSDR study search",
)


def server(input, output, session):
    # run the search once per click (or when the mode changes), the table and the details panel both use it
    @reactive.calc
    @reactive.event(input.go, input.mode)
    def found():
        filters = {column: input[fid]() for fid, (label, column) in FILTERS.items()}
        return search(input.query(), filters, mode=input.mode())

    @render.data_frame
    def results():
        return render.DataGrid(
            found()[TABLE_COLUMNS],
            width="100%",  # use the full page width
            height="70vh",
            selection_mode="row",  # click a row to select it
            styles=[
                {"cols": [0], "style": {"min-width": "90px"}},                         # Accession
                {"cols": [1], "style": {"min-width": "250px", "max-width": "400px"}},  # Study Title
                {"cols": [2], "style": {"max-width": "180px"}},                        # organism
            ],
        )

    @render.ui
    def details():
        selected = results.data_view(selected=True)
        if selected.empty:
            return ui.p("Click a study to see the details.")

        # look up the full row, the table only has a few columns
        acc = selected["Accession"].iloc[0]
        r = found().set_index("Accession").loc[acc]
        url = f"https://osdr.nasa.gov/bio/repo/data/studies/{acc}"

        # all fields in one paragraph with line breaks, the card puts a big gap between separate elements
        fields = []
        for label, col in DETAIL_FIELDS.items():
            if pd.notna(r[col]) and r[col] != "":
                fields += [ui.strong(f"{label}: "), str(r[col]), ui.br()]
        return ui.card(
            ui.card_header(r["Study Title"]),
            ui.p(ui.a(f"Open {acc} on OSDR ↗", href=url, target="_blank")),
            ui.p(*fields),
            ui.hr(),
            ui.p(r["Study Description"]),
            height="70vh",  # same height as the table, scrolls if longer
        )


app = App(app_ui, server)
