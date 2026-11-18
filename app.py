from dash_graphs import create_app

app=create_app(pdbid="1A8E", is_topoly=False)
app.run(debug=True, host='0.0.0.0', port=8014)
