"""Unbranded three-pan demonstration; this is not a universal product template."""
import bpy
from mathutils import Vector


def build(ctx):
    g,c=ctx.geometry,ctx.collection
    shell=g.material('Example dark shell','302420',metallic=.08,roughness=.24,coat=.4)
    gold=g.material('Example trim','BD985D',metallic=.8,roughness=.26)
    silver=g.material('Example mirror','E1E3E7',metallic=1,roughness=.07)
    stationary=[g.plate(c,'Base',(0,0,1.5),(100,52,3),3,shell)]
    stationary.append(g.ring(c,'Walls',(0,0,5.35),(100,52),(96,48),(3,2),5.5,shell))
    lid=[g.plate(c,'Lid',(0,0,10.8),(100,52,3),3,shell)]
    mirror=g.plate(c,'Mirror',(0,0,9.08),(90,42,.22),1.5,silver,edge_mm=.04)
    lid.append(mirror)
    stationary.append(g.cylinder(c,'Through pin',(0,28,8.8),.5,70,gold))
    for x,length,moving in [(-24,20,False),(0,26,True),(24,20,False)]:
        barrel=g.cylinder(c,f'Barrel {x}',(x,28,8.8),1.3,length,shell)
        cutter=g.cylinder(c,'Bore cutter',(x,28,8.8),.65,length+2)
        g.difference(barrel,cutter)
        bpy.data.objects.remove(cutter,do_unlink=True)
        (lid if moving else stationary).append(barrel)
        if not moving:
            stationary.append(g.plate(c,f'Base lug {x}',(x,26.5,6.8),(20,4,4),.8,shell))
    lid.append(g.plate(c,'Lid lug',(0,26.7,10.6),(26,2.5,1.2),.6,shell))
    foam=g.material('Example foam','151413',roughness=.9)
    fibers=g.material('Example bristle envelope','C7BFA5',roughness=.75)
    root,brush=g.applicator(c,'Removable applicator',(0,-17,4.7),46,4,['foam','bristle'],
                           dict(handle=shell,metal=gold,foam=foam,bristle=fibers))
    stationary+=brush
    world=bpy.data.worlds.new('Example world');world.use_nodes=True
    next(n for n in world.node_tree.nodes if n.type=='BACKGROUND').inputs[1].default_value=.25
    ctx.scene.world=world
    for name,loc,power,size in [('Key',(-100,-100,200),3,.16),('Fill',(100,80,150),2,.12)]:
        data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
        obj=bpy.data.objects.new(name,data);c.objects.link(obj);obj.location=Vector(loc)*g.MM;g.aim(obj,(0,0,10))
    camera_data=bpy.data.cameras.new('Product view');camera_data.type='ORTHO';camera_data.clip_start=.001
    camera=bpy.data.objects.new('Product view',camera_data);c.objects.link(camera);camera.location=Vector((100,-160,160))*g.MM;g.aim(camera,(0,0,15))
    ctx.scene.camera=camera
    return {'stationary':stationary,'moving':lid,'contents':brush,'mirror':mirror,'studio':[],
            'shots':{'open':{'camera':camera,'frame':20,'objects':stationary+lid},
                     'closed':{'camera':camera,'frame':1,'objects':stationary+lid}}}
