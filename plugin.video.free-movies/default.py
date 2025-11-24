import xbmcaddon, xbmcgui, xbmcplugin, sys

addon = xbmcaddon.Addon()
handle = int(sys.argv[1])

MOVIES = [
    ("Example Movie 1", "https://example.com/movie1.mp4"),
    ("Example Movie 2", "https://example.com/movie2.mp4")
]

def list_movies():
    for name, url in MOVIES:
        li = xbmcgui.ListItem(label=name)
        li.setInfo('video', {'title': name})
        li.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(handle, url, li, False)
    xbmcplugin.endOfDirectory(handle)

if __name__ == "__main__":
    list_movies()
