using UnityEngine;
namespace Qiling
{
    // Presentation consumes validated session results; visual collisions never award points.
    public sealed class Arena3D : MonoBehaviour
    {
        TrainingSession session; SwordTrajectory sword;
        Transform enemy, arm, shield, tip;
        LineRenderer blade, halo;
        Material armor, dark, glow, gold;
        Phase lastPhase; float clock, recoil, flash; int health, successes, playerHealth;
        public void Initialize(TrainingSession model, SwordTrajectory input, Camera camera)
        {
            session=model; sword=input; health=model.EnemyHealth; successes=model.Successes; playerHealth=model.PlayerHealth;
            camera.transform.position=new Vector3(0,3.4f,-8.4f); camera.transform.LookAt(new Vector3(0,1.6f,0)); camera.fieldOfView=52;
            camera.backgroundColor=new Color(.018f,.031f,.065f);
            RenderSettings.ambientLight=new Color(.3f,.4f,.55f);
            armor=Lit(new Color(.18f,.28f,.38f)); dark=Lit(new Color(.035f,.06f,.10f));
            glow=new Material(Resources.Load<Shader>("SwordGlow")); glow.color=new Color(.2f,1,.92f,.9f);
            gold=new Material(glow);gold.color=new Color(1,.55f,.15f,.85f);
            var light=new GameObject("Moonlight",typeof(Light)).GetComponent<Light>(); light.transform.SetParent(transform);light.type=LightType.Directional;light.intensity=1.4f;light.transform.rotation=Quaternion.Euler(35,-35,0);
            Shape("Training platform",PrimitiveType.Cylinder,transform,new Vector3(0,-.15f,0),new Vector3(9,.15f,9),dark);
            for(int r=1;r<5;r++) Ring("Floor light",transform,Vector3.up*.015f,r*1.0f,glow,.014f);
            for(int i=0;i<7;i++) {float a=(i-3)*Mathf.PI/6; Shape("Pillar",PrimitiveType.Cube,transform,new Vector3(Mathf.Sin(a)*6,1.5f,Mathf.Cos(a)*6),new Vector3(.25f,3,.25f),armor);}
            enemy=new GameObject("Guardian articulated rig").transform;enemy.SetParent(transform);enemy.position=new Vector3(0,0,.8f);
            Shape("Chest",PrimitiveType.Capsule,enemy,new Vector3(0,1.35f,0),new Vector3(.85f,.65f,.48f),armor);
            Shape("Head",PrimitiveType.Sphere,enemy,new Vector3(0,2.28f,0),Vector3.one*.5f,armor);
            Shape("Visor",PrimitiveType.Cube,enemy,new Vector3(0,2.3f,-.25f),new Vector3(.36f,.055f,.035f),gold);
            for(int i=-1;i<=1;i+=2) Shape("Leg",PrimitiveType.Capsule,enemy,new Vector3(i*.27f,.5f,0),new Vector3(.3f,.48f,.3f),dark);
            arm=new GameObject("Sword shoulder").transform; arm.SetParent(enemy,false);arm.localPosition=new Vector3(-.58f,1.8f,0);
            Shape("Arm",PrimitiveType.Capsule,arm,new Vector3(0,-.35f,0),new Vector3(.24f,.4f,.24f),armor);
            Shape("Enemy blade",PrimitiveType.Cube,arm,new Vector3(0,-1.35f,0),new Vector3(.07f,1.35f,.07f),gold);
            shield=Shape("Shield",PrimitiveType.Cube,enemy,new Vector3(.7f,1.35f,-.18f),new Vector3(.65f,1,.13f),armor);
            blade=Line("Player blade",transform,glow,.055f);halo=Line("Blade bloom",transform,glow,.15f);
            tip=new GameObject("Blade trail tip").transform;tip.SetParent(transform);
            var trail=tip.gameObject.AddComponent<TrailRenderer>();trail.sharedMaterial=glow;trail.time=.3f;trail.startWidth=.5f;trail.endWidth=0;trail.minVertexDistance=.025f;trail.emitting=false;
        }
        Material Lit(Color color) {var m=new Material(Resources.Load<Material>("ArenaLit"));m.color=color;return m;}
        static Transform Shape(string name,PrimitiveType type,Transform parent,Vector3 position,Vector3 scale,Material material)
        {var g=GameObject.CreatePrimitive(type);g.name=name;g.transform.SetParent(parent,false);g.transform.localPosition=position;g.transform.localScale=scale;g.GetComponent<Renderer>().sharedMaterial=material;Destroy(g.GetComponent<Collider>());return g.transform;}
        static LineRenderer Line(string name,Transform parent,Material mat,float width)
        {var g=new GameObject(name);g.transform.SetParent(parent,false);var l=g.AddComponent<LineRenderer>();l.sharedMaterial=mat;l.startWidth=l.endWidth=width;l.positionCount=2;return l;}
        static void Ring(string name,Transform parent,Vector3 center,float radius,Material mat,float width)
        {var l=Line(name,parent,mat,width);l.useWorldSpace=false;l.positionCount=65;for(int i=0;i<65;i++){float a=i*Mathf.PI/32;l.SetPosition(i,center+new Vector3(Mathf.Sin(a)*radius,0,Mathf.Cos(a)*radius));}}
        void Burst(Color color)
        {for(int i=0;i<16;i++){var g=Shape("Impact spark",PrimitiveType.Sphere,transform,new Vector3(0,1.5f,-.2f),Vector3.one*.055f,color.r>.8f?gold:glow);var p=g.gameObject.AddComponent<CombatSpark>();p.Velocity=Random.onUnitSphere*3;}}
        void Update()
        {
            if(session==null)return;
            bool paused=session.State==Phase.Paused||session.State==Phase.Reconcile;
            float dt=paused?0:Time.deltaTime;clock+=dt;recoil=Mathf.Max(0,recoil-dt);flash=Mathf.Max(0,flash-dt);
            if(session.Successes>successes||session.EnemyHealth<health){recoil=.5f;Burst(Color.cyan);}
            if(session.PlayerHealth<playerHealth)Burst(Color.red);
            if(lastPhase==Phase.Block && (session.State==Phase.Counter || session.State==Phase.ComboFirst || session.State==Phase.ChargeWait)){flash=.6f;Burst(Color.cyan);}
            lastPhase=session.State; health=session.EnemyHealth;successes=session.Successes;playerHealth=session.PlayerHealth;
            float wind=session.State==Phase.Telegraph?Mathf.Clamp01(1-session.Remaining/2):0;
            float strike=session.State==Phase.Block?Mathf.Sin(Mathf.Clamp01(1-session.Remaining/1.5f)*Mathf.PI):0;
            enemy.localPosition=new Vector3(0,Mathf.Sin(clock*2)*.035f,.8f-strike*.8f+recoil);
            enemy.localRotation=Quaternion.Euler(-recoil*35,Mathf.Sin(clock)*4,0);
            arm.localRotation=Quaternion.Euler(-wind*140+strike*80,0,-15-wind*40);
            shield.localRotation=Quaternion.Euler(0,Mathf.Sin(clock*2)*8,5);
            blade.SetPosition(0,sword.Grip);blade.SetPosition(1,sword.Tip);halo.SetPosition(0,sword.Grip);halo.SetPosition(1,sword.Tip);
            tip.position=sword.Tip;tip.GetComponent<TrailRenderer>().emitting=!paused&&sword.Moving;
        }
    }
    public sealed class CombatSpark:MonoBehaviour
    { public Vector3 Velocity;float remaining=.35f;void Update(){transform.position+=Velocity*Time.deltaTime;Velocity+=Vector3.down*Time.deltaTime*5;remaining-=Time.deltaTime;transform.localScale=Vector3.one*Mathf.Max(0,remaining)*.16f;if(remaining<=0)Destroy(gameObject);} }
}
