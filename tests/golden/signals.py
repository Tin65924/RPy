from roblox import Instance

part = Instance.new("Part")

def on_touch(hit):
    print(f"Touched by {hit.Name}")

part.Touched.Connect(on_touch)
part.Touched.Once(on_touch)
part.Touched.Wait()
